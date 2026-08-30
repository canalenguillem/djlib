from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.track import TrackOut


class CrateSummary(BaseModel):
    """Lo que hace falta para el listado, sin arrastrar todas las canciones."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime
    track_count: int = 0
    total_seconds: int = 0


class CrateDetail(CrateSummary):
    tracks: list[TrackOut] = []


class CrateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    # Permite guardar de golpe lo que hay filtrado en la biblioteca.
    track_ids: list[int] = []


class CrateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class CrateTrackAdd(BaseModel):
    track_id: int


class CrateReorder(BaseModel):
    """La lista completa en su nuevo orden, no movimientos sueltos."""

    track_ids: list[int]
