"""Catalogo de etiquetas: mood, estilo y momento de la noche."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.text import slugify
from app.core.time import utcnow
from app.models.tag import Tag, TagKind


class TagError(ValueError):
    pass


def list_tags(db: Session, kind: TagKind | None = None) -> list[Tag]:
    stmt = select(Tag).order_by(Tag.kind, Tag.name)
    if kind is not None:
        stmt = stmt.where(Tag.kind == kind)
    return list(db.scalars(stmt))


def get_by_id(db: Session, tag_id: int) -> Tag | None:
    return db.get(Tag, tag_id)


def get_by_slug(db: Session, kind: TagKind, slug: str) -> Tag | None:
    return db.scalar(select(Tag).where(Tag.kind == kind, Tag.slug == slug))


def create_tag(db: Session, *, kind: TagKind, name: str) -> Tag:
    name = name.strip()
    slug = slugify(name)
    if not slug:
        raise TagError("El nombre de la etiqueta no es valido.")
    if get_by_slug(db, kind, slug) is not None:
        raise TagError(f"Ya existe una etiqueta equivalente a '{name}' en esa categoria.")
    tag = Tag(kind=kind, name=name, slug=slug)
    db.add(tag)
    db.flush()
    return tag


def rename_tag(db: Session, tag: Tag, name: str) -> Tag:
    name = name.strip()
    slug = slugify(name)
    if not slug:
        raise TagError("El nombre de la etiqueta no es valido.")
    clash = get_by_slug(db, tag.kind, slug)
    if clash is not None and clash.id != tag.id:
        raise TagError(f"Ya existe una etiqueta equivalente a '{name}' en esa categoria.")
    tag.name = name
    tag.slug = slug
    tag.updated_at = utcnow()
    return tag


def get_many(db: Session, tag_ids: list[int]) -> list[Tag]:
    if not tag_ids:
        return []
    found = list(db.scalars(select(Tag).where(Tag.id.in_(tag_ids))))
    missing = set(tag_ids) - {t.id for t in found}
    if missing:
        raise TagError(f"Etiquetas inexistentes: {sorted(missing)}")
    return found
