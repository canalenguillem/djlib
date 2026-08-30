from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base


class CrateTrack(Base):
    """Una cancion dentro de un crate, en una posicion concreta.

    Se modela como entidad propia y no como tabla de union suelta porque el
    orden es el dato importante: un crate es una seleccion ordenada, que es
    justo lo que lo diferencia de un filtro.
    """

    __tablename__ = "crate_tracks"

    crate_id: Mapped[int] = mapped_column(
        ForeignKey("crates.id", ondelete="CASCADE"), primary_key=True
    )
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    crate: Mapped["Crate"] = relationship(back_populates="entries")
    track: Mapped["Track"] = relationship(lazy="selectin")  # noqa: F821


class Crate(Base):
    """Una seleccion de canciones con nombre y orden propio: "warm-up del
    sabado", "cierre 90s". A diferencia de un filtro, no cambia sola."""

    __tablename__ = "crates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    entries: Mapped[list[CrateTrack]] = relationship(
        back_populates="crate",
        cascade="all, delete-orphan",
        order_by="CrateTrack.position",
        lazy="selectin",
    )

    @property
    def tracks(self) -> list["Track"]:  # noqa: F821
        return [entry.track for entry in self.entries]

    @property
    def total_seconds(self) -> int:
        return sum(e.track.duration_seconds or 0 for e in self.entries)

    __table_args__ = (
        UniqueConstraint("slug", name="uq_crates_slug"),
        {"mysql_engine": "InnoDB"},
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Crate {self.id} {self.name!r} ({len(self.entries)})>"
