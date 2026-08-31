from pydantic import BaseModel

from app.schemas.track import SearchCandidate


class RecognitionStatus(BaseModel):
    """Para que el frontend sepa que puede ofrecer: grabar, subir capturas o
    ambas cosas. Cada una depende de una clave distinta."""

    enabled: bool
    provider: str | None = None
    screenshot_enabled: bool = False


class RecognitionResult(BaseModel):
    recognized: bool
    artist: str | None = None
    title: str | None = None
    album: str | None = None
    release_date: str | None = None
    song_link: str | None = None
    # Se devuelven ya los candidatos de YouTube: en el movil, con datos y en
    # mitad de un bar, ahorrar una vuelta al servidor se nota.
    candidates: list[SearchCandidate] = []


class DetectedSong(BaseModel):
    title: str
    artist: str | None = None


class ScreenshotResult(BaseModel):
    """Lo que se ha leido en la captura, en el orden en que aparece."""

    songs: list[DetectedSong] = []
