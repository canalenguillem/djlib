import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base


class ListenSource(str, enum.Enum):
    # Reproductor de la biblioteca, de un crate o la pagina Escuchar
    player = "player"
    # Un plato del mezclador
    mixer = "mixer"


class Listen(Base):
    """Una cancion que ha sonado de verdad, no solo que se ha cargado. Si se
    borra el usuario o la cancion, la escucha queda en los totales."""

    __tablename__ = "listens"
    __table_args__ = (Index("ix_listens_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    track_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[ListenSource] = mapped_column(
        Enum(ListenSource, name="listen_source", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
