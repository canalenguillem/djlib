from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models.tag import TagKind
from app.schemas.tag import TagCreate, TagOut, TagUpdate
from app.services import tag_service
from app.services.tag_service import TagError

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
def list_tags(current_user: CurrentUser, db: DbSession, kind: TagKind | None = None):
    return [TagOut.model_validate(t) for t in tag_service.list_tags(db, kind)]


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, current_user: CurrentUser, db: DbSession):
    try:
        tag = tag_service.create_tag(db, kind=payload.kind, name=payload.name)
        db.commit()
    except TagError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.refresh(tag)
    return TagOut.model_validate(tag)


@router.patch("/{tag_id}", response_model=TagOut)
def rename_tag(tag_id: int, payload: TagUpdate, current_user: CurrentUser, db: DbSession):
    tag = tag_service.get_by_id(db, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Etiqueta no encontrada.")
    try:
        tag_service.rename_tag(db, tag, payload.name)
        db.commit()
    except TagError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.refresh(tag)
    return TagOut.model_validate(tag)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: int, current_user: CurrentUser, db: DbSession):
    tag = tag_service.get_by_id(db, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Etiqueta no encontrada.")
    # La relacion con las canciones cae por ON DELETE CASCADE en track_tags.
    db.delete(tag)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
