from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Table, Column, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


album_media = Table(
    "album_media",
    Base.metadata,
    Column("album_id", Integer, ForeignKey("albums.id"), primary_key=True),
    Column("media_id", Integer, ForeignKey("media.id"), primary_key=True),
)

# 媒体-标签关联（source 区分 ai 生成 / manual 手动）
media_tags = Table(
    "media_tags",
    Base.metadata,
    Column("media_id", Integer, ForeignKey("media.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
    Column("source", String(8), default="ai", nullable=True),
)

# 点赞（一人一赞，可取消）
media_likes = Table(
    "media_likes",
    Base.metadata,
    Column("media_id", Integer, ForeignKey("media.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("created_at", DateTime, default=utcnow),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 存储文件名（uuid.ext），位于 data/originals/
    filename: Mapped[str] = mapped_column(String(128), unique=True)
    thumb_filename: Mapped[str | None] = mapped_column(String(128), nullable=True)
    orig_name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(16))  # photo / video
    mime_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 拍摄时间：EXIF DateTimeOriginal > 文件名时间戳 > 批次提示 > 文件 mtime > 上传时间
    taken_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    taken_at_source: Mapped[str] = mapped_column(String(16), default="upload")
    # 元数据：设备与地点（微信另存图可能全为空）
    camera_make: Mapped[str | None] = mapped_column(String(64), nullable=True)
    camera_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gps_lat: Mapped[float | None] = mapped_column(nullable=True)
    gps_lon: Mapped[float | None] = mapped_column(nullable=True)
    location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 内容哈希（sha256），用于批量导入去重
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    # 原始尺寸（瀑布流布局用），视频取缩略图尺寸
    width: Mapped[int | None] = mapped_column(nullable=True)
    height: Mapped[int | None] = mapped_column(nullable=True)
    # AI 建议（建议制：采用后覆盖 caption，二者独立保留）
    ai_caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_tagged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 点赞计数（冗余列，点赞时增减）
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    uploader_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    uploader = relationship("User")
    albums = relationship("Album", secondary=album_media, back_populates="media")
    tags = relationship("Tag", secondary=media_tags, lazy="selectin")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_type: Mapped[str] = mapped_column(String(16), index=True)  # media / album
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    author = relationship("User")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)


class LoginLog(Base):
    __tablename__ = "login_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)


class Album(Base):
    __tablename__ = "albums"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_media_id: Mapped[int | None] = mapped_column(ForeignKey("media.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    media = relationship("Media", secondary=album_media, back_populates="albums")
