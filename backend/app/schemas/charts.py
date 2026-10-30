from pydantic import BaseModel


class ChartSource(BaseModel):
    id: str
    name: str
    group: str


class ChartPosition(BaseModel):
    source: str
    position: int


class ChartTrackOut(BaseModel):
    # Con la mezcla, como en Beatport: es lo que se busca en YouTube
    title: str
    name: str
    mix: str | None = None
    artist: str
    bpm: int | None = None
    key: str | None = None
    duration_seconds: int | None = None
    image_url: str | None = None
    sample_url: str | None = None
    url: str | None = None
    positions: list[ChartPosition]
    score: float
    already_in_library: bool = False


class ChartError(BaseModel):
    source: str
    message: str


class ChartCombined(BaseModel):
    items: list[ChartTrackOut]
    errors: list[ChartError] = []
