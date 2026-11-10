"""系统信息与示例设置（出生日期、头像等）。"""

import os
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import ORIGINALS_DIR, THUMBS_DIR, AVATARS_DIR
from ..database import get_db
from ..models import Media, Setting, Tag, User
from ..services.ai_tagger import OLLAMA_URL, MODEL

router = APIRouter(prefix="/api", tags=["system"])

DEFAULT_BIRTH = "2024-01-01"


@router.get("/system/info")
def system_info(user=Depends(get_current_user), db: Session = Depends(get_db)):
    photos = db.scalar(select(func.count()).select_from(select(Media).where(Media.media_type == "photo").subquery())) or 0
    videos = db.scalar(select(func.count()).select_from(select(Media).where(Media.media_type == "video").subquery())) or 0
    tagged = db.scalar(select(func.count()).select_from(select(Media).where(Media.ai_tagged_at.is_not(None)).subquery())) or 0
    n_tags = db.scalar(select(func.count()).select_from(Tag)) or 0
    n_users = db.scalar(select(func.count()).select_from(User)) or 0

    def dir_size_mb(path):
        total = 0
        try:
            for name in os.listdir(path):
                p = os.path.join(path, name)
                if os.path.isfile(p):
                    total += os.path.getsize(p)
        except OSError:
            pass
        return round(total / 1048576, 1)

    ollama_ok = False
    try:
        import urllib.request

        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(OLLAMA_URL + "/api/tags", timeout=3) as resp:
            ollama_ok = resp.status == 200
    except Exception:
        ollama_ok = False

    return {
        "photos": photos,
        "videos": videos,
        "ai_tagged": tagged,
        "tags": n_tags,
        "users": n_users,
        "storage_originals_mb": dir_size_mb(ORIGINALS_DIR),
        "storage_thumbs_mb": dir_size_mb(THUMBS_DIR),
        "ai_model": MODEL,
        "ollama_ok": ollama_ok,
    }


@router.get("/settings")
def get_settings(user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = {r.key: r.value for r in db.scalars(select(Setting)).all()}
    avatar_ts = rows.get("avatar_ts")
    return {
        "birth_date": rows.get("birth_date") or DEFAULT_BIRTH,
        "avatar_url": f"/data/avatars/avatar.jpg?v={avatar_ts}" if avatar_ts else None,
    }


class SettingsIn(BaseModel):
    birth_date: str | None = None


@router.put("/settings")
def put_settings(data: SettingsIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if data.birth_date is not None:
        try:
            datetime.strptime(data.birth_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "生日格式应为 YYYY-MM-DD")
        row = db.get(Setting, "birth_date")
        if row:
            row.value = data.birth_date
        else:
            db.add(Setting(key="birth_date", value=data.birth_date))
        db.commit()
    return get_settings(user, db)


@router.post("/system/avatar")
async def upload_avatar(file: UploadFile = File(...), user=Depends(get_current_user), db: Session = Depends(get_db)):
    """自定义头像：服务端压到 512px JPEG，覆盖保存。"""
    import io
    import time

    from PIL import Image

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 10MB")
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        scale = min(1.0, 512 / max(img.width, img.height))
        if scale < 1.0:
            img = img.resize((int(img.width * scale), int(img.height * scale)))
        dest = os.path.join(AVATARS_DIR, "avatar.jpg")
        img.save(dest, format="JPEG", quality=88)
    except Exception:
        raise HTTPException(400, "图片格式无法识别（支持 jpg/png/webp）")

    ts = str(int(time.time()))
    row = db.get(Setting, "avatar_ts")
    if row:
        row.value = ts
    else:
        db.add(Setting(key="avatar_ts", value=ts))
    db.commit()
    return {"avatar_url": f"/data/avatars/avatar.jpg?v={ts}"}
