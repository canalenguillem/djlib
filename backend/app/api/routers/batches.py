from collections import Counter

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.batch import BatchStatus, DownloadBatch
from app.models.crate import Crate
from app.schemas.batch import BatchCreate, BatchItemOut, BatchOut, BatchSummary
from app.services import batch_service

router = APIRouter(prefix="/batches", tags=["batches"])

# Las tandas viejas no interesan en el listado
LISTADO = 20


def _summary(db, batch: DownloadBatch) -> dict:
    crate = db.get(Crate, batch.crate_id) if batch.crate_id else None
    return {
        "id": batch.id,
        "name": batch.name,
        "crate_id": batch.crate_id,
        "crate_name": crate.name if crate else None,
        "status": batch.status,
        "created_at": batch.created_at,
        "total": len(batch.items),
        "counts": dict(Counter(item.status for item in batch.items)),
    }


def _detail(db, batch: DownloadBatch) -> BatchOut:
    return BatchOut(
        **_summary(db, batch),
        items=[BatchItemOut.model_validate(item) for item in batch.items],
    )


def _get_or_404(db, batch_id: int, user_id: int) -> DownloadBatch:
    batch = db.get(DownloadBatch, batch_id)
    if batch is None or batch.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tanda no encontrada.")
    return batch


@router.post("", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def create_batch(payload: BatchCreate, current_user: CurrentUser, db: DbSession) -> BatchOut:
    """Deja las canciones en cola: el servidor las hace solo, una tras otra,
    aunque se cierre el navegador."""
    try:
        batch = batch_service.create_batch(
            db,
            current_user,
            payload.name,
            payload.crate_id,
            [(s.title, s.artist) for s in payload.songs],
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    db.refresh(batch)
    return _detail(db, batch)


@router.get("", response_model=list[BatchSummary])
def list_batches(current_user: CurrentUser, db: DbSession) -> list[BatchSummary]:
    """Las ultimas tandas del usuario, de la mas nueva a la mas vieja."""
    tandas = db.scalars(
        select(DownloadBatch)
        .where(DownloadBatch.user_id == current_user.id)
        .order_by(DownloadBatch.id.desc())
        .limit(LISTADO)
    )
    return [BatchSummary(**_summary(db, t)) for t in tandas]


@router.get("/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: int, current_user: CurrentUser, db: DbSession) -> BatchOut:
    return _detail(db, _get_or_404(db, batch_id, current_user.id))


@router.post("/{batch_id}/cancel", response_model=BatchOut)
def cancel_batch(batch_id: int, current_user: CurrentUser, db: DbSession) -> BatchOut:
    """Lo pendiente no se hara; lo que ya se esta descargando termina."""
    batch = _get_or_404(db, batch_id, current_user.id)
    if batch.status == BatchStatus.active:
        batch_service.cancel_batch(db, batch)
        db.commit()
        db.refresh(batch)
    return _detail(db, batch)
