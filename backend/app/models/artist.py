import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base

# Una cancion puede tener varios artistas y un artista varias canciones.
# `position` conserva el orden: principal primero, colaboraciones despues.
track_artists = Table(
    "track_artists",
    Base.metadata,
    Column("track_id", ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
    Column("artist_id", ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, nullable=False, default=0),
    mysql_engine="InnoDB",
)


class EnrichmentStatus(str, enum.Enum):
    """Como fue la ultima consulta a las fuentes externas."""

    pending = "pending"      # creado, aun sin consultar
    ok = "ok"                # se encontro y se relleno
    not_found = "not_found"  # existe el artista pero las fuentes no lo conocen
    error = "error"          # fallo de red o de la API
    manual = "manual"        # editado a mano: no se pisa automaticamente


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Nombre normalizado: evita "Blur" y "blur " como dos artistas distintos.
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)

    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    begin_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "Group", "Person"... tal y como lo clasifica MusicBrainz
    artist_type: Mapped[str | None] = mapped_column(String(40), nullable=True)

    musicbrainz_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    wikipedia_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    enrichment_status: Mapped[EnrichmentStatus] = mapped_column(
        Enum(
            EnrichmentStatus,
            name="enrichment_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=EnrichmentStatus.pending,
    )
    enrichment_error: Mapped[str | None] = mapped_column(String(400), nullable=True)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    tracks: Mapped[list["Track"]] = relationship(  # noqa: F821
        secondary=track_artists, back_populates="artists", order_by="Track.title"
    )
    relations: Mapped[list["ArtistRelation"]] = relationship(
        back_populates="artist",
        cascade="all, delete-orphan",
        foreign_keys="ArtistRelation.artist_id",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Artist {self.id} {self.name!r}>"


class ArtistRelation(Base):
    """Vinculo con otro artista: "Robbie Williams fue miembro de Take That".

    El relacionado puede no estar en la biblioteca, asi que se guarda siempre su
    nombre y solo se enlaza con `related_artist_id` cuando tambien existe aqui.
    """

    __tablename__ = "artist_relations"

    id: Mapped[int] = mapped_column(primary_key=True)
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    related_artist_id: Mapped[int | None] = mapped_column(
        ForeignKey("artists.id", ondelete="SET NULL"), nullable=True
    )
    related_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # "member of band", "collaboration", "founder"... viene de MusicBrainz
    relation_type: Mapped[str] = mapped_column(String(60), nullable=False)
    related_musicbrainz_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    artist: Mapped["Artist"] = relationship(
        back_populates="relations", foreign_keys=[artist_id]
    )

    __table_args__ = (
        UniqueConstraint(
            "artist_id", "related_name", "relation_type", name="uq_artist_relation"
        ),
        {"mysql_engine": "InnoDB"},
    )
