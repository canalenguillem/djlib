from pydantic import BaseModel


class BeatportGenre(BaseModel):
    id: int
    name: str


class BeatportTrackOut(BaseModel):
    position: int
    # Con la mezcla, que es lo que distingue una version de otra y lo que
    # conviene buscar en YouTube: "Zoolander (Extended Mix)"
    title: str
    name: str
    mix: str | None = None
    artist: str
    remixers: str | None = None
    bpm: int | None = None
    key: str | None = None
    genre: str | None = None
    label: str | None = None
    length: str | None = None
    release_date: str | None = None
    image_url: str | None = None
    sample_url: str | None = None
    beatport_url: str
    already_in_library: bool = False


class BeatportTop(BaseModel):
    genre: BeatportGenre | None = None
    items: list[BeatportTrackOut] = []
