from pydantic import BaseModel


class SpotifyStatus(BaseModel):
    """Que puede ofrecer el frontend: conectar, o ya conectado."""

    enabled: bool
    connected: bool
    display_name: str | None = None


class SpotifyAuthUrl(BaseModel):
    url: str


class PlayedTrackOut(BaseModel):
    title: str
    artist: str
    album: str | None = None
    played_at: str | None = None
    spotify_url: str | None = None
    image_url: str | None = None
    # Para no volver a bajar lo que ya esta
    already_in_library: bool = False


class RecentlyPlayed(BaseModel):
    items: list[PlayedTrackOut] = []
