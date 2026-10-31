"""Las ultimas busquedas en YouTube de cada usuario."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.search import SearchHistory
from app.models.user import User

# Las que se guardan por usuario; las mas viejas se borran
MAXIMO = 100


def _limpio(valor: str | None) -> str | None:
    return (valor or "").strip()[:300] or None


def record(db: Session, user: User, title: str | None, artist: str | None, version: str | None, results: int) -> None:
    title, artist = _limpio(title), _limpio(artist)
    misma = db.scalars(
        select(SearchHistory).where(
            SearchHistory.user_id == user.id,
            SearchHistory.title == title if title else SearchHistory.title.is_(None),
            SearchHistory.artist == artist if artist else SearchHistory.artist.is_(None),
            SearchHistory.version == version if version else SearchHistory.version.is_(None),
        )
    ).first()
    # Se borra y se vuelve a crear, no se actualiza: la fecha va a segundos y
    # dos busquedas seguidas empatarian; el id nuevo deja claro cual es la ultima
    if misma:
        db.delete(misma)
    db.add(SearchHistory(user_id=user.id, title=title, artist=artist, version=version, results=results, created_at=utcnow()))
    db.flush()
    sobran = db.scalars(
        select(SearchHistory.id)
        .where(SearchHistory.user_id == user.id)
        .order_by(SearchHistory.created_at.desc(), SearchHistory.id.desc())
        .offset(MAXIMO)
    ).all()
    if sobran:
        db.execute(delete(SearchHistory).where(SearchHistory.id.in_(sobran)))


def recent(db: Session, user: User, limit: int) -> list[SearchHistory]:
    return list(
        db.scalars(
            select(SearchHistory)
            .where(SearchHistory.user_id == user.id)
            .order_by(SearchHistory.created_at.desc(), SearchHistory.id.desc())
            .limit(limit)
        )
    )


def clear(db: Session, user: User) -> None:
    db.execute(delete(SearchHistory).where(SearchHistory.user_id == user.id))
