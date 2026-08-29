from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.tag import TagKind


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: TagKind
    name: str
    slug: str
    created_at: datetime


class TagCreate(BaseModel):
    kind: TagKind
    name: str = Field(min_length=1, max_length=80)


class TagUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
