from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.track import TrackSource, TrackStatus
from app.schemas.artist import ArtistBrief
from app.schemas.tag import TagOut


class TrackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    artist_text: str | None = None
    duration_seconds: int | None = None
    ingest_source: TrackSource
    request_query: str
    source_url: str | None = None
    source_site: str | None = None
    source_video_id: str | None = None
    status: TrackStatus
    error_message: str | None = None
    file_size: int | None = None
    bpm: int | None = None
    added_by_user_id: int | None = None
    downloaded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    tags: list[TagOut] = []
    artists: list[ArtistBrief] = []


class TrackPage(BaseModel):
    items: list[TrackOut]
    total: int
    limit: int
    offset: int


class TrackFromUrl(BaseModel):
    url: str = Field(min_length=5, max_length=500)


class TrackFromSearch(BaseModel):
    """Basta con uno de los dos. Solo con el artista se piden sus temas mas
    relevantes, que es como se explora a alguien de quien no recuerdas titulos."""

    title: str | None = Field(default=None, max_length=300)
    artist: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def al_menos_uno(self) -> "TrackFromSearch":
        if not (self.title or "").strip() and not (self.artist or "").strip():
            raise ValueError("Indica un titulo, un artista, o los dos.")
        return self


class TrackUpdate(BaseModel):
    """Correccion manual de los metadatos que yt-dlp haya inferido mal."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    artist_text: str | None = Field(default=None, max_length=300)


class TrackTagsUpdate(BaseModel):
    tag_ids: list[int] = []


class SearchCandidate(BaseModel):
    """Un resultado de YouTube tal y como se le ofrece al usuario."""

    video_id: str
    title: str
    channel: str | None = None
    duration_seconds: int | None = None
    url: str
    thumbnail_url: str | None = None
    # Marcas para que se vea de un vistazo que conviene y que no
    already_in_library: bool = False
    too_long: bool = False


class SearchResults(BaseModel):
    query: str
    candidates: list[SearchCandidate]
