from datetime import datetime
from pydantic import BaseModel


class RegisterIn(BaseModel):
    username: str
    password: str
    invite_code: str


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MediaPatch(BaseModel):
    caption: str | None = None
    taken_at: datetime | None = None


class MediaOut(BaseModel):
    id: int
    orig_name: str
    media_type: str
    mime_type: str
    size: int
    caption: str | None
    taken_at: datetime
    taken_at_source: str
    created_at: datetime
    uploader_id: int
    camera_make: str | None = None
    camera_model: str | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None
    location_name: str | None = None
    width: int | None = None
    height: int | None = None
    comment_count: int | None = None
    likes_count: int = 0
    liked_by_me: bool = False
    ai_caption: str | None = None
    ai_tagged_at: datetime | None = None
    tags: list[dict] = []
    url: str = ""
    thumbnail_url: str | None = None

    class Config:
        from_attributes = True


class CommentIn(BaseModel):
    target_type: str  # media / album
    target_id: int
    body: str


class CommentOut(BaseModel):
    id: int
    target_type: str
    target_id: int
    author_id: int
    author_name: str | None = None
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


class AlbumIn(BaseModel):
    name: str
    description: str | None = None
    cover_media_id: int | None = None


class AlbumOut(BaseModel):
    id: int
    name: str
    description: str | None
    cover_media_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class TagOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True
