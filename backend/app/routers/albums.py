"""相册与标签：本阶段仅建表 + 基础 CRUD 骨架。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Album, Tag, User
from ..schemas import AlbumIn, AlbumOut, TagOut

album_router = APIRouter(prefix="/api/albums", tags=["albums"])
tag_router = APIRouter(prefix="/api/tags", tags=["tags"])


# ---- Albums ----

@album_router.get("", response_model=list[AlbumOut])
def list_albums(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Album).order_by(Album.created_at.desc())).all()


@album_router.post("", response_model=AlbumOut)
def create_album(data: AlbumIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    album = Album(name=data.name.strip(), description=data.description, cover_media_id=data.cover_media_id)
    db.add(album)
    db.commit()
    db.refresh(album)
    return album


@album_router.get("/{album_id}", response_model=AlbumOut)
def get_album(album_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    album = db.get(Album, album_id)
    if not album:
        raise HTTPException(404, "相册不存在")
    return album


@album_router.patch("/{album_id}", response_model=AlbumOut)
def update_album(
    album_id: int,
    data: AlbumIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    album = db.get(Album, album_id)
    if not album:
        raise HTTPException(404, "相册不存在")
    album.name = data.name.strip()
    album.description = data.description
    album.cover_media_id = data.cover_media_id
    db.commit()
    db.refresh(album)
    return album


@album_router.delete("/{album_id}")
def delete_album(album_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    album = db.get(Album, album_id)
    if not album:
        raise HTTPException(404, "相册不存在")
    db.delete(album)
    db.commit()
    return {"ok": True}


# ---- Tags ----

@tag_router.get("", response_model=list[TagOut])
def list_tags(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Tag).order_by(Tag.name)).all()


@tag_router.post("", response_model=TagOut)
def create_tag(name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = name.strip()
    if not name:
        raise HTTPException(400, "标签名不能为空")
    tag = db.scalar(select(Tag).where(Tag.name == name))
    if tag:
        return tag
    tag = Tag(name=name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag
