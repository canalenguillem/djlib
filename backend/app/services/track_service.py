"""Biblioteca de canciones: alta, descarga en segundo plano, filtrado y borrado."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.text import normalize_key
from app.core.time import utcnow
from app.models.artist import EnrichmentStatus
from app.models.tag import Tag
from app.models.track import Track, TrackSource, TrackStatus, track_tags
from app.models.user import User
from app.services import artist_service, downloader
from app.services.downloader import DownloadError

logger = logging.getLogger(__name__)

# Estados en los que una cancion "ocupa sitio" a efectos de deduplicacion.
LIVE_STATUSES = (TrackStatus.pending, TrackStatus.downloading, TrackStatus.ready)


class DuplicateTrackError(ValueError):
    def __init__(self, existing: Track) -> None:
        super().__init__(f"'{existing.title}' ya esta en la biblioteca.")
        self.existing = existing


def music_dir() -> Path:
    return Path(settings.music_dir)


# --- Alta -------------------------------------------------------------------


def _find_by_video_id(db: Session, video_id: str) -> Track | None:
    return db.scalar(
        select(Track)
        .where(Track.source_video_id == video_id, Track.status.in_(LIVE_STATUSES))
        .limit(1)
    )


def _find_by_normalized_key(db: Session, key: str) -> Track | None:
    return db.scalar(
        select(Track)
        .where(Track.normalized_key == key, Track.status.in_(LIVE_STATUSES))
        .limit(1)
    )


def create_from_url(db: Session, user: User, url: str) -> Track:
    url = url.strip()
    if not downloader.is_supported_url(url):
        raise ValueError("Introduce una URL que empiece por http:// o https://")

    # Si es de YouTube podemos deducir el id sin salir a la red y avisar del
    # duplicado al instante, antes de crear nada.
    video_id = downloader.extract_youtube_id(url)
    if video_id:
        existing = _find_by_video_id(db, video_id)
        if existing is not None:
            raise DuplicateTrackError(existing)

    track = Track(
        title=url,  # provisional: lo sustituye el titulo real al resolver
        ingest_source=TrackSource.url,
        request_query=url,
        source_url=url,
        source_video_id=video_id,
        status=TrackStatus.pending,
        added_by_user_id=user.id,
    )
    db.add(track)
    db.flush()
    return track


def create_from_search(db: Session, user: User, title: str, artist: str | None) -> Track:
    title = title.strip()
    if not title:
        raise ValueError("Indica al menos el titulo de la cancion.")
    artist = (artist or "").strip() or None

    key = normalize_key(artist, title)
    existing = _find_by_normalized_key(db, key)
    if existing is not None:
        raise DuplicateTrackError(existing)

    label = " - ".join(part for part in (artist, title) if part)
    track = Track(
        title=title,
        artist_text=artist,
        ingest_source=TrackSource.search,
        request_query=label,
        normalized_key=key,
        status=TrackStatus.pending,
        added_by_user_id=user.id,
    )
    db.add(track)
    db.flush()
    return track


# --- Descarga en segundo plano ----------------------------------------------


def _query_for(track: Track) -> str:
    if track.ingest_source == TrackSource.url and track.source_url:
        return track.source_url
    return downloader.search_query(track.title, track.artist_text)


def run_download(session_factory, track_id: int) -> None:
    """Resuelve metadatos, deduplica y descarga. Se ejecuta fuera del ciclo de
    la peticion, asi que abre y cierra su propia sesion de base de datos."""
    with session_factory() as db:
        track = db.get(Track, track_id)
        if track is None or track.status != TrackStatus.pending:
            return
        track.status = TrackStatus.downloading
        track.updated_at = utcnow()
        db.commit()
        query = _query_for(track)

    try:
        info = downloader.resolve(query)

        if info.duration_seconds and info.duration_seconds > settings.max_track_duration_seconds:
            raise DownloadError(
                f"El audio dura {info.duration_seconds // 60} minutos, demasiado "
                "para la biblioteca."
            )

        # Ahora que conocemos el id real, deduplicamos otra vez: la busqueda por
        # titulo puede acabar en un video que ya teniamos por URL.
        with session_factory() as db:
            duplicate = db.scalar(
                select(Track)
                .where(
                    Track.source_video_id == info.video_id,
                    Track.status.in_(LIVE_STATUSES),
                    Track.id != track_id,
                )
                .limit(1)
            )
            if duplicate is not None:
                _fail(session_factory, track_id, f"'{duplicate.title}' ya esta en la biblioteca.")
                return

        # Se descarga la URL ya resuelta, no la consulta: repetir la busqueda
        # podria dar otro resultado, y con varios candidatos se bajarian todos.
        path = downloader.download(info.webpage_url or query, music_dir(), info.video_id)

    except DownloadError as exc:
        _fail(session_factory, track_id, str(exc))
        return
    except Exception:  # pragma: no cover - salvavidas: nunca dejar en 'downloading'
        logger.exception("Fallo inesperado descargando el track %s", track_id)
        _fail(session_factory, track_id, "Error inesperado durante la descarga.")
        return

    with session_factory() as db:
        track = db.get(Track, track_id)
        if track is None:  # lo han borrado mientras se descargaba
            path.unlink(missing_ok=True)
            return
        track.title = info.title
        track.artist_text = info.artist
        track.duration_seconds = info.duration_seconds
        track.source_url = info.webpage_url or track.source_url
        track.source_site = info.site
        track.source_video_id = info.video_id
        track.normalized_key = normalize_key(info.artist, info.title)
        track.file_path = str(path)
        track.file_size = path.stat().st_size
        track.status = TrackStatus.ready
        track.error_message = None
        track.downloaded_at = utcnow()
        track.updated_at = utcnow()

        # La ficha del artista se crea sola al descargar: asi queda documentado
        # quien toca esto para la proxima vez que suene.
        artists = artist_service.link_track_artists(db, track)
        pending_ids = [
            a.id for a in artists if a.enrichment_status == EnrichmentStatus.pending
        ]
        db.commit()

    # Fuera de la transaccion: pedir datos a MusicBrainz/Wikipedia es lento y no
    # debe retrasar el que la cancion aparezca ya como lista.
    if pending_ids:
        artist_service.run_enrichment(session_factory, pending_ids)


def _fail(session_factory, track_id: int, message: str) -> None:
    with session_factory() as db:
        track = db.get(Track, track_id)
        if track is None:
            return
        track.status = TrackStatus.error
        track.error_message = message
        track.updated_at = utcnow()
        db.commit()


def recover_interrupted(db: Session) -> int:
    """Al arrancar, las descargas que se quedaron a medias por un reinicio no
    tienen quien las continue: se marcan como error para que se vean y se
    puedan reintentar."""
    stuck = list(
        db.scalars(
            select(Track).where(
                Track.status.in_((TrackStatus.pending, TrackStatus.downloading))
            )
        )
    )
    for track in stuck:
        track.status = TrackStatus.error
        track.error_message = "Descarga interrumpida al reiniciar el servidor."
        track.updated_at = utcnow()
    if stuck:
        db.commit()
    return len(stuck)


# --- Consulta ---------------------------------------------------------------


def list_tracks(
    db: Session,
    *,
    search: str | None = None,
    status: TrackStatus | None = None,
    tag_ids: list[int] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Track], int]:
    stmt = select(Track)

    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(Track.title.like(pattern), Track.artist_text.like(pattern)))
    if status is not None:
        stmt = stmt.where(Track.status == status)

    # Filtro combinado: la cancion debe llevar TODAS las etiquetas pedidas
    # ("warm-up" Y "britanica" Y "chill"), no cualquiera de ellas.
    for tag_id in tag_ids or []:
        stmt = stmt.where(
            Track.id.in_(select(track_tags.c.track_id).where(track_tags.c.tag_id == tag_id))
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    rows = list(
        db.scalars(stmt.order_by(Track.created_at.desc()).limit(limit).offset(offset))
    )
    return rows, total


def get_by_id(db: Session, track_id: int) -> Track | None:
    return db.get(Track, track_id)


# --- Edicion y borrado ------------------------------------------------------


def set_tags(db: Session, track: Track, tags: list[Tag]) -> Track:
    track.tags = tags
    track.updated_at = utcnow()
    return track


def delete_track(db: Session, track: Track) -> None:
    """Borra el registro y el mp3. El fichero primero: si falla, no queremos
    perder la fila que apunta a el."""
    path = Path(track.file_path) if track.file_path else None
    db.delete(track)
    db.commit()
    if path is not None:
        try:
            path.unlink(missing_ok=True)
        except OSError:  # pragma: no cover
            logger.warning("No se pudo borrar el fichero %s", path)


def download_filename(track: Track) -> str:
    """Nombre bonito para el navegador; en disco se llama <video_id>.mp3."""
    parts = [p for p in (track.artist_text, track.title) if p]
    raw = " - ".join(parts) or "track"
    safe = "".join(c if c.isalnum() or c in " -_.()[]" else "_" for c in raw)
    return f"{safe.strip()[:120]}.mp3"
