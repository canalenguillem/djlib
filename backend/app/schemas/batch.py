from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.track import Version


class BatchSong(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    artist: str | None = Field(default=None, max_length=300)


class BatchCreate(BaseModel):
    """Canciones para que el servidor las busque y descargue solo."""

    name: str = Field(min_length=1, max_length=200)
    crate_id: int | None = None
    # Buscar de cada una esa version para DJ; sin ella, la normal
    version: Version | None = None
    songs: list[BatchSong] = Field(min_length=1, max_length=1000)


class BatchItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    title: str
    artist: str | None = None
    status: str
    video_title: str | None = None
    track_id: int | None = None
    message: str | None = None


class BatchSummary(BaseModel):
    id: int
    name: str
    crate_id: int | None = None
    crate_name: str | None = None
    version: str | None = None
    status: str
    created_at: datetime
    total: int
    # Cuantas hay en cada estado, p. ej. {"done": 12, "pending": 3}
    counts: dict[str, int]
    # Lo que se esta buscando o descargando ahora mismo, p. ej. "Blur - Song 2"
    current: list[str] = []


class BatchOut(BatchSummary):
    items: list[BatchItemOut]
