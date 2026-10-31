"""Tandas de descarga que hace el servidor solo.

El navegador manda la lista (de una captura, de una playlist) y se puede
cerrar: unos hilos del propio backend van cogiendo canciones pendientes, las
buscan en YouTube, descargan el primer resultado que no sea un mix y las meten
en el crate elegido. Todo el estado esta en la base de datos, asi que un
reinicio del servidor no pierde nada: al arrancar se retoma donde se quedo.
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utcnow
from app.models.batch import (
    OPEN_ITEM_STATUSES,
    BatchItemStatus,
    BatchStatus,
    DownloadBatch,
    DownloadBatchItem,
)
from app.models.crate import Crate
from app.models.track import Track, TrackStatus
from app.models.user import User
from app.services import downloader, track_service
from app.services.downloader import DownloadError

# Menos que esto es un avance o un trozo para redes, no la cancion: pasa mucho
# con extended y mashups, que se anuncian con 20 segundos en YouTube
MIN_SEGUNDOS = 90
NOMBRE_VERSION = {"extended": "extended", "remix": "remix", "mashup": "mashup", "edit": "DJ edit"}

logger = logging.getLogger(__name__)

# Sin trabajo, cada cuanto se vuelve a mirar
ESPERA_SEGUNDOS = 3.0


# --- Alta y consulta --------------------------------------------------------


def create_batch(
    db: Session,
    user: User,
    name: str,
    crate_id: int | None,
    songs: list[tuple[str, str | None]],
    version: str | None = None,
) -> DownloadBatch:
    """Crea la tanda con sus canciones pendientes. LookupError si el crate no
    existe."""
    if crate_id is not None and db.get(Crate, crate_id) is None:
        raise LookupError("Crate no encontrado.")
    batch = DownloadBatch(
        user_id=user.id, name=name.strip()[:200] or "Descargas", crate_id=crate_id, version=version
    )
    for posicion, (titulo, artista) in enumerate(songs):
        batch.items.append(
            DownloadBatchItem(
                position=posicion,
                title=titulo.strip()[:300],
                artist=(artista or "").strip()[:300] or None,
            )
        )
    db.add(batch)
    db.flush()
    return batch


def cancel_batch(db: Session, batch: DownloadBatch) -> None:
    """Lo pendiente no se hara; lo que ya esta en marcha termina."""
    batch.status = BatchStatus.cancelled
    for item in batch.items:
        if item.status == BatchItemStatus.pending:
            item.status = BatchItemStatus.cancelled
    batch.updated_at = utcnow()


def _cerrar_si_terminada(db: Session, batch_id: int) -> None:
    batch = db.get(DownloadBatch, batch_id)
    if batch is None or batch.status != BatchStatus.active:
        return
    abiertas = db.scalar(
        select(DownloadBatchItem.id)
        .where(
            DownloadBatchItem.batch_id == batch_id,
            DownloadBatchItem.status.in_(OPEN_ITEM_STATUSES),
        )
        .limit(1)
    )
    if abiertas is None:
        batch.status = BatchStatus.done
        batch.updated_at = utcnow()


# --- Trabajo ----------------------------------------------------------------


def _reclamar(session_factory) -> int | None:
    """La siguiente cancion pendiente, marcada como en curso para que ningun
    otro hilo (ni otro proceso) la coja tambien."""
    with session_factory() as db:
        candidatas = db.scalars(
            select(DownloadBatchItem.id)
            .join(DownloadBatch)
            .where(
                DownloadBatchItem.status == BatchItemStatus.pending,
                DownloadBatch.status == BatchStatus.active,
            )
            .order_by(DownloadBatchItem.batch_id, DownloadBatchItem.position)
            .limit(5)
        ).all()
        for item_id in candidatas:
            # Solo gana quien la cambia de verdad de pendiente a en curso
            resultado = db.execute(
                update(DownloadBatchItem)
                .where(
                    DownloadBatchItem.id == item_id,
                    DownloadBatchItem.status == BatchItemStatus.pending,
                )
                .values(status=BatchItemStatus.searching, updated_at=utcnow())
            )
            db.commit()
            if resultado.rowcount == 1:
                return item_id
    return None


def _poner(session_factory, item_id: int, status: BatchItemStatus, **campos) -> None:
    with session_factory() as db:
        item = db.get(DownloadBatchItem, item_id)
        if item is None:
            return
        item.status = status
        for campo, valor in campos.items():
            setattr(item, campo, valor)
        item.updated_at = utcnow()
        if status not in OPEN_ITEM_STATUSES:
            db.flush()  # para que la consulta de abiertas ya no la cuente
            _cerrar_si_terminada(db, item.batch_id)
        db.commit()


def process_item(session_factory, item_id: int) -> None:
    """Busca, descarga y mete en el crate una cancion de una tanda."""
    with session_factory() as db:
        item = db.get(DownloadBatchItem, item_id)
        if item is None:
            return
        batch = item.batch
        titulo, artista, crate_id, version = item.title, item.artist, batch.crate_id, batch.version
        user = db.get(User, batch.user_id) if batch.user_id else None
        track_id = item.track_id

    # Retomada tras un reinicio: la descarga ya estaba lanzada
    if track_id is not None:
        _esperar_descarga(session_factory, item_id, track_id)
        return

    try:
        resultados = downloader.search(titulo, artista, version)
    except DownloadError as exc:
        _poner(session_factory, item_id, BatchItemStatus.error, message=str(exc))
        return

    limite = settings.max_song_duration_seconds
    # El primero de YouTube que no sea un mix de una hora y, si se pidio una
    # version, que lo diga el titulo: YouTube devuelve la normal cuando no hay
    # otra, y bajarla como si fuera un mashup engañaria
    elegido = next(
        (
            r
            for r in resultados
            if not (r.duration_seconds and r.duration_seconds > limite)
            and not (r.duration_seconds and r.duration_seconds < MIN_SEGUNDOS)
            and downloader.es_version(r.title, version)
        ),
        None,
    )
    if elegido is None:
        _poner(
            session_factory,
            item_id,
            BatchItemStatus.not_found,
            message=f"No hay versión {NOMBRE_VERSION[version]} en YouTube." if version else None,
        )
        return

    with session_factory() as db:
        existente = track_service.existing_by_video_id(db, [elegido.video_id]).get(elegido.video_id)
        if existente is None and user is not None:
            try:
                nueva = track_service.create_from_url(
                    db, db.merge(user), elegido.url, crate_id=crate_id
                )
                db.commit()
                track_id = nueva.id
            except track_service.DuplicateTrackError as exc:
                db.rollback()
                existente = exc.existing
            except (ValueError, LookupError) as exc:
                db.rollback()
                _poner(session_factory, item_id, BatchItemStatus.error, message=str(exc))
                return

        if existente is not None:
            # Ya la tenias: solo se mete en el crate
            if crate_id is not None:
                try:
                    track_service.move_to_crate(db, existente, crate_id, None)
                    db.commit()
                except LookupError:
                    db.rollback()  # el crate se ha borrado mientras tanto
            _poner(
                session_factory,
                item_id,
                BatchItemStatus.already,
                track_id=existente.id,
                video_title=elegido.title[:300],
            )
            return

    if track_id is None:
        _poner(session_factory, item_id, BatchItemStatus.error, message="La tanda no tiene usuario.")
        return

    _poner(
        session_factory,
        item_id,
        BatchItemStatus.downloading,
        track_id=track_id,
        video_title=elegido.title[:300],
    )
    # En este mismo hilo: asi solo hay tantas descargas a la vez como hilos
    track_service.run_download(session_factory, track_id)
    _esperar_descarga(session_factory, item_id, track_id)


def _esperar_descarga(session_factory, item_id: int, track_id: int) -> None:
    """Deja la cancion de la tanda segun como haya acabado su descarga."""
    with session_factory() as db:
        track = db.get(Track, track_id)
        estado = track.status if track else None
        mensaje = track.error_message if track else "La cancion se ha borrado."
    if estado == TrackStatus.pending:
        # Retomada tras un reinicio: se descarga ahora
        track_service.run_download(session_factory, track_id)
        with session_factory() as db:
            track = db.get(Track, track_id)
            estado = track.status if track else None
            mensaje = track.error_message if track else "La cancion se ha borrado."
    if estado == TrackStatus.ready:
        _poner(session_factory, item_id, BatchItemStatus.done)
    else:
        _poner(session_factory, item_id, BatchItemStatus.error, message=mensaje)


def process_next(session_factory) -> bool:
    """Hace una cancion pendiente, si la hay. Devuelve si habia trabajo."""
    item_id = _reclamar(session_factory)
    if item_id is None:
        return False
    try:
        process_item(session_factory, item_id)
    except Exception:  # pragma: no cover - salvavidas: el hilo no debe morir
        logger.exception("Fallo inesperado en la cancion %s de una tanda", item_id)
        _poner(session_factory, item_id, BatchItemStatus.error, message="Error inesperado.")
    return True


# --- Arranque ---------------------------------------------------------------


def recover(db: Session) -> int:
    """Al arrancar, lo que estaba en curso se devuelve a la cola. Las descargas
    lanzadas ya se habran marcado como error al recuperar las canciones: se
    vuelven a poner pendientes para que la tanda las reintente."""
    en_curso = list(
        db.scalars(
            select(DownloadBatchItem).where(
                DownloadBatchItem.status.in_(
                    (BatchItemStatus.searching, BatchItemStatus.downloading)
                )
            )
        )
    )
    for item in en_curso:
        if item.track_id is not None:
            track = db.get(Track, item.track_id)
            if track is not None and track.status == TrackStatus.error:
                track.status = TrackStatus.pending
                track.error_message = None
                track.updated_at = utcnow()
        item.status = BatchItemStatus.pending
        item.updated_at = utcnow()
    if en_curso:
        db.commit()
    return len(en_curso)


_parar = threading.Event()


def start_workers(session_factory, cantidad: int) -> None:
    """Arranca los hilos que van haciendo las tandas. Tantos como descargas a
    la vez se quieran: cada uno hace una cancion entera antes de coger otra."""
    _parar.clear()

    def bucle() -> None:
        while not _parar.is_set():
            try:
                hubo = process_next(session_factory)
            except Exception:  # pragma: no cover - p. ej. la base de datos caida
                logger.exception("Fallo en el trabajador de tandas")
                hubo = False
            if not hubo:
                _parar.wait(ESPERA_SEGUNDOS)

    for numero in range(cantidad):
        threading.Thread(target=bucle, name=f"tandas-{numero}", daemon=True).start()


def stop_workers() -> None:
    _parar.set()
