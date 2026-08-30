from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUser, DbSession
from app.core.time import utcnow
from app.models.crate import Crate
from app.schemas.crate import (
    CrateCreate,
    CrateDetail,
    CrateReorder,
    CrateSummary,
    CrateTrackAdd,
    CrateUpdate,
)
from app.schemas.track import TrackOut
from app.services import crate_service
from app.services.crate_service import CrateError

router = APIRouter(prefix="/crates", tags=["crates"])


def _summary(crate: Crate) -> CrateSummary:
    resumen = CrateSummary.model_validate(crate)
    resumen.track_count = len(crate.entries)
    resumen.total_seconds = crate.total_seconds
    return resumen


def _detail(crate: Crate) -> CrateDetail:
    detalle = CrateDetail.model_validate(crate)
    detalle.track_count = len(crate.entries)
    detalle.total_seconds = crate.total_seconds
    detalle.tracks = [TrackOut.model_validate(t) for t in crate.tracks]
    return detalle


def _get_or_404(db, crate_id: int) -> Crate:
    crate = crate_service.get_by_id(db, crate_id)
    if crate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crate no encontrado.")
    return crate


def _conflicto(exc: CrateError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("", response_model=list[CrateSummary])
def list_crates(current_user: CurrentUser, db: DbSession):
    return [_summary(c) for c in crate_service.list_crates(db)]


@router.post("", response_model=CrateDetail, status_code=status.HTTP_201_CREATED)
def create_crate(payload: CrateCreate, current_user: CurrentUser, db: DbSession) -> CrateDetail:
    try:
        crate = crate_service.create_crate(
            db,
            name=payload.name,
            user=current_user,
            description=payload.description,
            track_ids=payload.track_ids,
        )
        db.commit()
    except CrateError as exc:
        db.rollback()
        raise _conflicto(exc) from exc
    db.refresh(crate)
    return _detail(crate)


@router.get("/{crate_id}", response_model=CrateDetail)
def get_crate(crate_id: int, current_user: CurrentUser, db: DbSession) -> CrateDetail:
    return _detail(_get_or_404(db, crate_id))


@router.patch("/{crate_id}", response_model=CrateDetail)
def update_crate(
    crate_id: int, payload: CrateUpdate, current_user: CurrentUser, db: DbSession
) -> CrateDetail:
    crate = _get_or_404(db, crate_id)
    datos = payload.model_dump(exclude_unset=True)
    try:
        if "name" in datos and datos["name"]:
            crate_service.rename_crate(db, crate, datos["name"])
        if "description" in datos:
            crate.description = (datos["description"] or "").strip() or None
            crate.updated_at = utcnow()
        db.commit()
    except CrateError as exc:
        db.rollback()
        raise _conflicto(exc) from exc
    db.refresh(crate)
    return _detail(crate)


@router.delete("/{crate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_crate(crate_id: int, current_user: CurrentUser, db: DbSession) -> Response:
    crate = _get_or_404(db, crate_id)
    db.delete(crate)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{crate_id}/tracks", response_model=CrateDetail)
def add_track(
    crate_id: int, payload: CrateTrackAdd, current_user: CurrentUser, db: DbSession
) -> CrateDetail:
    crate = _get_or_404(db, crate_id)
    try:
        crate_service.add_track(db, crate, payload.track_id)
        db.commit()
    except CrateError as exc:
        db.rollback()
        raise _conflicto(exc) from exc
    db.refresh(crate)
    return _detail(crate)


@router.delete("/{crate_id}/tracks/{track_id}", response_model=CrateDetail)
def remove_track(
    crate_id: int, track_id: int, current_user: CurrentUser, db: DbSession
) -> CrateDetail:
    crate = _get_or_404(db, crate_id)
    try:
        crate_service.remove_track(db, crate, track_id)
        db.commit()
    except CrateError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.refresh(crate)
    return _detail(crate)


@router.put("/{crate_id}/order", response_model=CrateDetail)
def reorder_crate(
    crate_id: int, payload: CrateReorder, current_user: CurrentUser, db: DbSession
) -> CrateDetail:
    """Fija el orden mandando la lista completa: dos reordenaciones seguidas no
    pueden dejar el crate en un estado a medias."""
    crate = _get_or_404(db, crate_id)
    try:
        crate_service.reorder(db, crate, payload.track_ids)
        db.commit()
    except CrateError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.refresh(crate)
    return _detail(crate)
