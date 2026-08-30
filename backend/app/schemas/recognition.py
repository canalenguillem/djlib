from pydantic import BaseModel

from app.schemas.track import SearchCandidate


class RecognitionStatus(BaseModel):
    """Para que el frontend sepa si puede ofrecer la pantalla de grabacion."""

    enabled: bool
    provider: str | None = None


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
