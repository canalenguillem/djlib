import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base


class BatchStatus(str, enum.Enum):
    active = "active"
    done = "done"
    cancelled = "cancelled"


class BatchItemStatus(str, enum.Enum):
    pending = "pending"
    searching = "searching"
    downloading = "downloading"
    # Descargada y en el crate
    done = "done"
    # Ya estaba en la biblioteca: solo se ha metido en el crate
    already = "already"
    not_found = "not_found"
    error = "error"
    cancelled = "cancelled"


# Lo que aun puede cambiar; el resto ya ha terminado
OPEN_ITEM_STATUSES = (
    BatchItemStatus.pending,
    BatchItemStatus.searching,
    BatchItemStatus.downloading,
)


class DownloadBatch(Base):
    """Una tanda de canciones que el servidor busca y descarga solo, una tras
    otra, sin necesitar el navegador abierto: la lista de una captura o de una
    playlist de Spotify."""

    __tablename__ = "download_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # De donde salen las canciones, p. ej. "Spotify: Warm-up" o "Capturas"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    crate_id: Mapped[int | None] = mapped_column(
        ForeignKey("crates.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=BatchStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    items: Mapped[list["DownloadBatchItem"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="DownloadBatchItem.position",
        lazy="selectin",
    )

    __table_args__ = ({"mysql_engine": "InnoDB"},)


class DownloadBatchItem(Base):
    __tablename__ = "download_batch_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("download_batches.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    artist: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BatchItemStatus.pending
    )
    # El video elegido en YouTube y la cancion de la biblioteca resultante
    video_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    track_id: Mapped[int | None] = mapped_column(
        ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    batch: Mapped[DownloadBatch] = relationship(back_populates="items")

    __table_args__ = (
        # El trabajador busca siempre "la siguiente pendiente"
        Index("ix_download_batch_items_status", "status", "batch_id", "position"),
        {"mysql_engine": "InnoDB"},
    )
