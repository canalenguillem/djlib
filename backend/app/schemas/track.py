from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.track import TrackSource, TrackStatus
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


class TrackPage(BaseModel):
    items: list[TrackOut]
    total: int
    limit: int
    offset: int


class TrackFromUrl(BaseModel):
    url: str = Field(min_length=5, max_length=500)


class TrackFromSearch(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    artist: str | None = Field(default=None, max_length=300)


class TrackUpdate(BaseModel):
    """Correccion manual de los metadatos que yt-dlp haya inferido mal."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    artist_text: str | None = Field(default=None, max_length=300)


class TrackTagsUpdate(BaseModel):
    tag_ids: list[int] = []
