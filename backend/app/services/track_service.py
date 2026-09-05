"""Biblioteca de canciones: alta, descarga en segundo plano, filtrado y borrado."""

from __future__ import annotations

import logging
import uuid
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
from app.services import artist_service, audio_file, bpm as bpm_service, downloader
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


def create_from_search(
    db: Session, user: User, title: str | None, artist: str | None
) -> Track:
    title = (title or "").strip() or None
    artist = (artist or "").strip() or None
    if not title and not artist:
        raise ValueError("Indica un titulo, un artista, o los dos.")

    # Sin titulo no se puede deducir que cancion es hasta resolverla, asi que
    # no hay clave por nombre con la que deduplicar todavia: lo hara el id de
    # video en cuanto YouTube conteste.
    key = normalize_key(artist, title) if title else None
    if key:
        existing = _find_by_normalized_key(db, key)
        if existing is not None:
            raise DuplicateTrackError(existing)

    label = " - ".join(part for part in (artist, title) if part)
    track = Track(
        title=title or label,
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


def create_from_upload(
    db: Session,
    user: User,
    *,
    contenido: bytes,
    filename: str,
    title: str | None = None,
    artist: str | None = None,
) -> Track:
    """Da de alta un fichero que sube el usuario desde su ordenador.

    A diferencia de las descargas, aqui no hay nada que esperar: el fichero ya
    esta, asi que la cancion nace directamente en estado `ready`.
    """
    extension = audio_file.normalize_extension(filename)

    destino = music_dir()
    destino.mkdir(parents=True, exist_ok=True)
    # Nombre propio, sin relacion con el original: los ficheros que llegan de
    # fuera traen acentos, espacios y caracteres de todo tipo.
    nombre = f"up_{uuid.uuid4().hex}{extension}"
    ruta = destino / nombre
    ruta.write_bytes(contenido)

    try:
        metadatos = audio_file.probe(ruta)
    except audio_file.AudioFileError:
        ruta.unlink(missing_ok=True)
        raise

    titulo = (title or "").strip() or metadatos.title or Path(filename).stem
    interprete = (artist or "").strip() or metadatos.artist

    clave = normalize_key(interprete, titulo)
    existente = _find_by_normalized_key(db, clave)
    if existente is not None:
        ruta.unlink(missing_ok=True)
        raise DuplicateTrackError(existente)

    track = Track(
        title=titulo,
        artist_text=interprete,
        duration_seconds=metadatos.duration_seconds,
        ingest_source=TrackSource.upload,
        request_query=filename[:500],
        source_site="upload",
        normalized_key=clave,
        file_path=str(ruta),
        file_size=ruta.stat().st_size,
        status=TrackStatus.ready,
        downloaded_at=utcnow(),
        added_by_user_id=user.id,
    )
    db.add(track)
    db.flush()
    return track


# --- Descarga en segundo plano ----------------------------------------------


def _query_for(track: Track) -> str:
    if track.ingest_source == TrackSource.url and track.source_url:
        return track.source_url
    return downloader.search_query_for_request(track.request_query)


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

    # Los generos llegan con el enriquecido, asi que las etiquetas de estilo se
    # ponen despues, no antes.
    with session_factory() as db:
        track = db.get(Track, track_id)
        if track is not None:
            artist_service.apply_style_tags(db, track)
            db.commit()

    analyze_bpm(session_factory, track_id)


def _fail(session_factory, track_id: int, message: str) -> None:
    with session_factory() as db:
        track = db.get(Track, track_id)
        if track is None:
            return
        track.status = TrackStatus.error
        track.error_message = message
        track.updated_at = utcnow()
        db.commit()


def analyze_bpm(session_factory, track_id: int, *, force: bool = False) -> int | None:
    """Detecta el tempo y lo guarda. Pensado para tareas en segundo plano.

    Sin `force` no toca un BPM ya existente: puede haberlo corregido el usuario,
    que sabe mejor que ningun detector a que velocidad va su musica.
    """
    if not settings.bpm_analysis_enabled:
        return None

    with session_factory() as db:
        track = db.get(Track, track_id)
        if track is None or not track.file_path or track.status != TrackStatus.ready:
            return None
        if track.bpm is not None and not force:
            return track.bpm
        ruta = Path(track.file_path)

    try:
        detectado = bpm_service.analyze(ruta)
    except bpm_service.BpmError as exc:
        logger.info("No se pudo analizar el tempo del track %s: %s", track_id, exc)
        return None
    except Exception:  # pragma: no cover - nunca tumbar la tarea de fondo
        logger.exception("Fallo inesperado analizando el tempo del track %s", track_id)
        return None

    if detectado is None:
        return None

    with session_factory() as db:
        track = db.get(Track, track_id)
        if track is None:
            return None
        track.bpm = detectado
        track.updated_at = utcnow()
        db.commit()
    return detectado


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
    energy_min: int | None = None,
    energy_max: int | None = None,
    bpm_min: int | None = None,
    bpm_max: int | None = None,
    sort: str = "recent",
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Track], int]:
    stmt = select(Track)

    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(Track.title.like(pattern), Track.artist_text.like(pattern)))
    if status is not None:
        stmt = stmt.where(Track.status == status)
    if energy_min is not None:
        stmt = stmt.where(Track.energy >= energy_min)
    if energy_max is not None:
        stmt = stmt.where(Track.energy <= energy_max)
    # Filtrar por horquilla de tempo es como se busca un tema para encajar en
    # una mezcla: "algo entre 122 y 126".
    if bpm_min is not None:
        stmt = stmt.where(Track.bpm >= bpm_min)
    if bpm_max is not None:
        stmt = stmt.where(Track.bpm <= bpm_max)

    # Filtro combinado: la cancion debe llevar TODAS las etiquetas pedidas
    # ("warm-up" Y "britanica" Y "chill"), no cualquiera de ellas.
    for tag_id in tag_ids or []:
        stmt = stmt.where(
            Track.id.in_(select(track_tags.c.track_id).where(track_tags.c.tag_id == tag_id))
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    # Ordenar por energia sirve para montar la curva de una noche: de los
    # temas tranquilos del principio a los del pico.
    # MariaDB no admite NULLS LAST, asi que se emula con una clave previa:
    # las que no tienen energia asignada quedan siempre al final.
    sin_energia = Track.energy.is_(None)
    ordenes = {
        "recent": (Track.created_at.desc(),),
        "energy": (sin_energia, Track.energy.desc(), Track.title),
        "energy_asc": (sin_energia, Track.energy.asc(), Track.title),
        "bpm": (Track.bpm.is_(None), Track.bpm, Track.title),
        "title": (Track.title,),
    }
    rows = list(
        db.scalars(
            stmt.order_by(*ordenes.get(sort, ordenes["recent"])).limit(limit).offset(offset)
        )
    )
    return rows, total


def get_by_id(db: Session, track_id: int) -> Track | None:
    return db.get(Track, track_id)


def existing_video_ids(db: Session, video_ids: list[str]) -> set[str]:
    """De una lista de ids de video, cuales ya estan en la biblioteca."""
    if not video_ids:
        return set()
    return set(
        db.scalars(
            select(Track.source_video_id).where(
                Track.source_video_id.in_(video_ids),
                Track.status.in_(LIVE_STATUSES),
            )
        )
    )


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


# Tipo MIME segun la extension del flujo que sirviera YouTube.
MEDIA_TYPES = {
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".opus": "audio/ogg",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".wav": "audio/wav",
}


def media_type(path: Path) -> str:
    return MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


def download_filename(track: Track) -> str:
    """Nombre bonito para el navegador; en disco se llama <video_id>.<ext>."""
    parts = [p for p in (track.artist_text, track.title) if p]
    raw = " - ".join(parts) or "track"
    safe = "".join(c if c.isalnum() or c in " -_.()[]" else "_" for c in raw)
    extension = Path(track.file_path).suffix if track.file_path else ".m4a"
    return f"{safe.strip()[:120]}{extension}"
