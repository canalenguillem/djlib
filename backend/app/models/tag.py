import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base
from app.models.track import track_tags


class TagKind(str, enum.Enum):
    """Los tres ejes de clasificacion del briefing."""

    mood = "mood"    # chill, euforico, oscuro...
    style = "style"  # britpop, hip hop, pop espanol...
    moment = "moment"  # warm-up, prime time, cierre...


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[TagKind] = mapped_column(
        Enum(TagKind, name="tag_kind", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Version normalizada del nombre: evita "80s" y "Ochentas" duplicados.
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    tracks: Mapped[list["Track"]] = relationship(  # noqa: F821
        secondary=track_tags, back_populates="tags"
    )

    __table_args__ = (
        UniqueConstraint("kind", "slug", name="uq_tags_kind_slug"),
        {"mysql_engine": "InnoDB"},
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Tag {self.id} {self.kind.value}:{self.slug}>"
