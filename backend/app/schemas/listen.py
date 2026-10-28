from datetime import datetime

from pydantic import BaseModel

from app.models.listen import ListenSource


class ListenCreate(BaseModel):
    track_id: int
    source: ListenSource


class ListenCounts(BaseModel):
    player: int = 0
    mixer: int = 0


class UserListens(BaseModel):
    user_id: int | None
    username: str | None
    total: ListenCounts
    last_7_days: ListenCounts
    last_listen_at: datetime | None


class TopTrack(BaseModel):
    track_id: int
    title: str
    artist_text: str | None
    player: int
    mixer: int


class ListenStats(BaseModel):
    users: list[UserListens]
    top_tracks: list[TopTrack]
