from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, DbSession, SessionFactory
from app.core.time import utcnow
from app.models.track import TrackStatus
from app.schemas.track import (
    TrackFromSearch,
    TrackFromUrl,
    TrackOut,
    TrackPage,
    TrackTagsUpdate,
    TrackUpdate,
)
from app.services import tag_service, track_service
from app.services.tag_service import TagError
from app.services.track_service import DuplicateTrackError

router = APIRouter(prefix="/tracks", tags=["tracks"])


def _schedule(background: BackgroundTasks, session_factory, track_id: int) -> None:
    """La descarga arranca cuando la respuesta ya ha salido, con su propia
    sesion de base de datos (la de la peticion ya estara cerrada)."""
    background.add_task(track_service.run_download, session_factory, track_id)


@router.get("", response_model=TrackPage)
def list_tracks(
    current_user: CurrentUser,
    db: DbSession,
    search: str | None = None,
    status_filter: TrackStatus | None = Query(default=None, alias="status"),
    tag_ids: list[int] = Query(default=[], alias="tag_id"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> TrackPage:
    items, total = track_service.list_tracks(
        db,
        search=search,
        status=status_filter,
        tag_ids=tag_ids,
        limit=limit,
        offset=offset,
    )
    return TrackPage(
        items=[TrackOut.model_validate(t) for t in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/from-url", response_model=TrackOut, status_code=status.HTTP_202_ACCEPTED)
def add_from_url(
    payload: TrackFromUrl,
    background: BackgroundTasks,
    current_user: CurrentUser,
    db: DbSession,
    session_factory: SessionFactory,
) -> TrackOut:
    try:
        track = track_service.create_from_url(db, current_user, payload.url)
    except DuplicateTrackError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(track)
    result = TrackOut.model_validate(track)
    _schedule(background, session_factory, track.id)
    return result


@router.post("/search", response_model=TrackOut, status_code=status.HTTP_202_ACCEPTED)
def add_from_search(
    payload: TrackFromSearch,
    background: BackgroundTasks,
    current_user: CurrentUser,
    db: DbSession,
    session_factory: SessionFactory,
) -> TrackOut:
    try:
        track = track_service.create_from_search(db, current_user, payload.title, payload.artist)
    except DuplicateTrackError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(track)
    result = TrackOut.model_validate(track)
    _schedule(background, session_factory, track.id)
    return result


def _get_or_404(db, track_id: int):
    track = track_service.get_by_id(db, track_id)
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cancion no encontrada.")
    return track


@router.get("/{track_id}", response_model=TrackOut)
def get_track(track_id: int, current_user: CurrentUser, db: DbSession) -> TrackOut:
    return TrackOut.model_validate(_get_or_404(db, track_id))


@router.patch("/{track_id}", response_model=TrackOut)
def update_track(
    track_id: int, payload: TrackUpdate, current_user: CurrentUser, db: DbSession
) -> TrackOut:
    track = _get_or_404(db, track_id)
    if payload.title is not None:
        track.title = payload.title.strip()
    if payload.artist_text is not None:
        track.artist_text = payload.artist_text.strip() or None
    track.updated_at = utcnow()
    db.commit()
    db.refresh(track)
    return TrackOut.model_validate(track)


@router.put("/{track_id}/tags", response_model=TrackOut)
def set_track_tags(
    track_id: int, payload: TrackTagsUpdate, current_user: CurrentUser, db: DbSession
) -> TrackOut:
    track = _get_or_404(db, track_id)
    try:
        tags = tag_service.get_many(db, payload.tag_ids)
    except TagError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    track_service.set_tags(db, track, tags)
    db.commit()
    db.refresh(track)
    return TrackOut.model_validate(track)


@router.post("/{track_id}/retry", response_model=TrackOut, status_code=status.HTTP_202_ACCEPTED)
def retry_track(
    track_id: int,
    background: BackgroundTasks,
    current_user: CurrentUser,
    db: DbSession,
    session_factory: SessionFactory,
) -> TrackOut:
    track = _get_or_404(db, track_id)
    if track.status != TrackStatus.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden reintentar las descargas que han fallado.",
        )
    track.status = TrackStatus.pending
    track.error_message = None
    track.updated_at = utcnow()
    db.commit()
    db.refresh(track)
    result = TrackOut.model_validate(track)
    _schedule(background, session_factory, track.id)
    return result


@router.get("/{track_id}/file")
def get_track_file(track_id: int, current_user: CurrentUser, db: DbSession):
    """Sirve el mp3 para reproducir o descargar. Soporta peticiones Range, que
    es lo que permite mover la barra del reproductor sin bajar todo el fichero."""
    track = _get_or_404(db, track_id)
    if track.status != TrackStatus.ready or not track.file_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="La cancion todavia no esta lista."
        )
    path = Path(track.file_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="El fichero ya no esta en el disco del servidor.",
        )
    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=track_service.download_filename(track),
        content_disposition_type="inline",
    )


@router.delete("/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_track(track_id: int, current_user: CurrentUser, db: DbSession) -> Response:
    track = _get_or_404(db, track_id)
    track_service.delete_track(db, track)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
