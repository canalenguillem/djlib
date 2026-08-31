from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.artist import EnrichmentStatus


class ArtistBrief(BaseModel):
    """Lo justo para enlazar desde una cancion a su ficha."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class ArtistRelationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    related_name: str
    relation_type: str
    related_artist_id: int | None = None


class ArtistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    bio: str | None = None
    country: str | None = None
    begin_year: int | None = None
    end_year: int | None = None
    artist_type: str | None = None
    musicbrainz_id: str | None = None
    wikipedia_url: str | None = None
    image_url: str | None = None
    channel_url: str | None = None
    follower_count: int | None = None
    enrichment_status: EnrichmentStatus
    enrichment_error: str | None = None
    enriched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    relations: list[ArtistRelationOut] = []
    track_count: int = 0


class ArtistPage(BaseModel):
    items: list[ArtistOut]
    total: int
    limit: int
    offset: int


class ArtistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ArtistUpdate(BaseModel):
    """Edicion manual. Cualquier campo enviado marca la ficha como `manual`,
    y a partir de ahi el enriquecido automatico deja de pisarla."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    bio: str | None = None
    country: str | None = Field(default=None, max_length=80)
    begin_year: int | None = Field(default=None, ge=1000, le=2999)
    end_year: int | None = Field(default=None, ge=1000, le=2999)
    wikipedia_url: str | None = Field(default=None, max_length=500)
    image_url: str | None = Field(default=None, max_length=700)


class TrackArtistsUpdate(BaseModel):
    names: list[str] = []
