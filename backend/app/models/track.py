import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base

# Relacion N:M entre canciones y etiquetas. Tabla simple, sin campos propios.
track_tags = Table(
    "track_tags",
    Base.metadata,
    Column("track_id", ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    mysql_engine="InnoDB",
)


class TrackStatus(str, enum.Enum):
    """Ciclo de vida de una descarga."""

    pending = "pending"        # en cola, aun no ha empezado
    downloading = "downloading"  # yt-dlp trabajando
    ready = "ready"            # mp3 en disco y utilizable
    error = "error"            # fallo o duplicado; error_message explica que paso


class TrackSource(str, enum.Enum):
    url = "url"        # el usuario pego un enlace
    search = "search"  # el usuario escribio titulo + artista
    recognition = "recognition"  # llego por reconocimiento de audio
    upload = "upload"  # fichero propio subido desde el ordenador


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    artist_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Origen
    ingest_source: Mapped[TrackSource] = mapped_column(
        Enum(
            TrackSource,
            name="track_source",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=TrackSource.url,
    )
    # Lo que pidio el usuario: la URL pegada o "artista - titulo" de la busqueda.
    request_query: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_site: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Identificador del video en su plataforma: la clave de deduplicacion.
    source_video_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Fichero
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    status: Mapped[TrackStatus] = mapped_column(
        Enum(
            TrackStatus,
            name="track_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=TrackStatus.pending,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Para deduplicar por nombre cuando no hay id de video (ver normalize_text)
    normalized_key: Mapped[str | None] = mapped_column(String(400), nullable=True)

    bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)  # fase 2
    # Intensidad de 1 a 5, como las estrellas que usan los DJ: 1 para el
    # warm-up, 5 para el pico de la noche. No es una nota de calidad.
    # El indice se declara abajo en __table_args__, junto a los demas
    energy: Mapped[int | None] = mapped_column(Integer, nullable=True)

    added_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    added_by: Mapped["User | None"] = relationship()  # noqa: F821
    artists: Mapped[list["Artist"]] = relationship(  # noqa: F821
        secondary="track_artists",
        back_populates="tracks",
        lazy="selectin",
        order_by="track_artists.c.position",
    )
    tags: Mapped[list["Tag"]] = relationship(  # noqa: F821
        secondary=track_tags, back_populates="tracks", lazy="selectin", order_by="Tag.name"
    )

    __table_args__ = (
        Index("ix_tracks_normalized_key", "normalized_key"),
        Index("ix_tracks_energy", "energy"),
        Index("ix_tracks_source_video_id", "source_video_id"),
        {"mysql_engine": "InnoDB"},
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Track {self.id} {self.title!r} {self.status.value}>"
