import hashlib
import mimetypes
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import ORIGINALS_DIR, THUMBS_DIR, TMP_DIR, ALLOWED_PHOTO_EXT, ALLOWED_VIDEO_EXT, ALLOWED_AUDIO_EXT
from ..database import get_db
from ..models import Comment, Media, Tag, User, media_likes, media_tags
from ..schemas import CommentIn, CommentOut, MediaOut, MediaPatch
from ..services.ai_tagger import tag_image
from ..services.exif import extract_metadata, parse_hint_datetime
from ..services.geocode import reverse_geocode
from ..services.thumbnails import get_dimensions, make_thumbnail
from ..services.videos import transcode_to_720p
from ..services.audio import normalize_audio

router = APIRouter(prefix="/api/media", tags=["media"])

def _comment_out(c: Comment) -> CommentOut:
    return CommentOut(
        id=c.id,
        target_type=c.target_type,
        target_id=c.target_id,
        author_id=c.author_id,
        author_name=c.author.username if c.author else None,
        body=c.body,
        created_at=c.created_at,
    )


COMMENT_TARGET = "media"


def _detect_media_type(ext: str) -> str | None:
    """按扩展名判媒体类型；不在白名单返回 None。"""
    if ext in ALLOWED_PHOTO_EXT:
        return "photo"
    if ext in ALLOWED_VIDEO_EXT:
        return "video"
    if ext in ALLOWED_AUDIO_EXT:
        return "audio"
    return None


def media_url(media: Media) -> str:
    return f"/data/originals/{media.filename}"


def thumb_url(media: Media) -> str | None:
    if media.thumb_filename:
        return f"/data/thumbnails/{media.thumb_filename}"
    return None


def to_out(media: Media, comment_count: int | None = None, tags: list | None = None, liked_by_me: bool | None = None) -> MediaOut:
    # 只用表列构造，避免 from_attributes 拉到 tags 关系的 ORM 对象导致校验失败
    data = {c.name: getattr(media, c.name) for c in Media.__table__.columns}
    out = MediaOut(**data)
    out.url = media_url(media)
    out.thumbnail_url = thumb_url(media)
    if comment_count is not None:
        out.comment_count = comment_count
    if tags is not None:
        out.tags = tags
    if liked_by_me is not None:
        out.liked_by_me = liked_by_me
    return out


def _batch_tags(db: Session, ids: list[int]) -> dict[int, list[dict]]:
    """批量取媒体标签 [{id,name}]，避免 N+1。"""
    if not ids:
        return {}
    rows = db.execute(
        select(media_tags.c.media_id, Tag.id, Tag.name)
        .join(Tag, Tag.id == media_tags.c.tag_id)
        .where(media_tags.c.media_id.in_(ids))
    ).all()
    d: dict[int, list[dict]] = {}
    for mid, tid, name in rows:
        d.setdefault(mid, []).append({"id": tid, "name": name})
    return d


@router.post("/upload")
async def upload(
    files: list[UploadFile] = File(...),
    taken_at_hint: str | None = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """批量上传。

    taken_at_hint：批次拍摄时间提示（如 2025-03 / 2025-03-15），用于
    EXIF 和文件名都解析不出的微信图。时间优先级：
    EXIF > 文件名时间戳 > taken_at_hint > 文件 mtime > 上传时间。
    同内容文件（sha256）自动去重跳过。
    返回 {items: MediaOut[], skipped: 重复跳过数}。
    """
    if not files:
        raise HTTPException(400, "未选择文件")
    hint_dt = parse_hint_datetime(taken_at_hint or "") if taken_at_hint else None
    results = []
    skipped = 0
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        media_type = _detect_media_type(ext)
        if media_type is None:
            raise HTTPException(400, f"不支持的文件类型: {ext}（文件 {f.filename}）")

        filename = f"{uuid.uuid4().hex}{ext}"
        dest = Path(ORIGINALS_DIR) / filename
        size = 0
        sha = hashlib.sha256()
        with open(dest, "wb") as out:
            while chunk := await f.read(1024 * 1024):
                size += len(chunk)
                sha.update(chunk)
                out.write(chunk)
        content_hash = sha.hexdigest()

        # 内容去重：同哈希已有记录则跳过（丢弃刚落盘的文件）
        dup = db.scalar(select(Media).where(Media.content_hash == content_hash))
        if dup is not None:
            skipped += 1
            try:
                dest.unlink(missing_ok=True)
            except OSError:
                pass
            continue

        media, dup_flag = _process_final_file(dest, size, content_hash, f.filename or filename, taken_at_hint, user, db)
        if dup_flag:
            skipped += 1
            try:
                dest.unlink(missing_ok=True)
            except OSError:
                pass
            continue
        if media.media_type == "video":
            background_tasks.add_task(_transcode_bg, media.id, str(dest))
        elif media.media_type == "audio":
            background_tasks.add_task(_normalize_audio_bg, media.id, str(dest))
        if media.media_type == "photo":
            background_tasks.add_task(_ai_tag_bg, media.id, str(dest))
        results.append(to_out(media))
    return {"items": results, "skipped": skipped}


# ---- 分片上传（移动端弱网友好）：init → chunk*N → finalize ----
# 每片独立请求，网络抖动最多损失一片；断点可续传（status 查已收片）。

def _valid_upload_id(upload_id: str) -> bool:
    return upload_id.isalnum() and len(upload_id) == 32


def _process_final_file(dest: Path, size: int, content_hash: str, orig_name: str,
                        taken_at_hint: str | None, user: User, db: Session):
    """finalize 共用管线：元数据 → 去重 → 缩略图 → 入库。返回 (media|None, skipped)"""
    hint_dt = parse_hint_datetime(taken_at_hint or "") if taken_at_hint else None
    meta = extract_metadata(dest, orig_name=orig_name)
    taken_at = meta["taken_at"]
    taken_at_source = meta["taken_at_source"]
    if taken_at is None or taken_at_source in ("file_mtime", "upload"):
        if hint_dt is not None:
            taken_at = hint_dt
            taken_at_source = "hint"
        elif taken_at is None:
            taken_at = meta["taken_at"]
            taken_at_source = meta["taken_at_source"] or "upload"

    dup = db.scalar(select(Media).where(Media.content_hash == content_hash))
    if dup is not None:
        return None, 1

    ext = os.path.splitext(orig_name)[1].lower()
    media_type = _detect_media_type(ext)
    if media_type is None:  # 理论上 finalize 前置校验已拦，双保险
        media_type = "photo"
    thumb_name = make_thumbnail(dest, media_type)
    # 尺寸：照片取原图，视频取缩略图（宽高比一致）
    dims = get_dimensions(dest) if media_type == "photo" else None
    if dims is None and thumb_name:
        dims = get_dimensions(os.path.join(THUMBS_DIR, thumb_name))
    location_name = None
    if meta["gps_lat"] is not None:
        location_name = reverse_geocode(meta["gps_lat"], meta["gps_lon"])

    media = Media(
        filename=dest.name,
        thumb_filename=thumb_name,
        orig_name=orig_name,
        media_type=media_type,
        mime_type=mimetypes.guess_type(orig_name)[0] or "application/octet-stream",
        size=size,
        taken_at=taken_at,
        taken_at_source=taken_at_source,
        camera_make=meta["camera_make"],
        camera_model=meta["camera_model"],
        gps_lat=meta["gps_lat"],
        gps_lon=meta["gps_lon"],
        location_name=location_name,
        content_hash=content_hash,
        width=dims[0] if dims else None,
        height=dims[1] if dims else None,
        uploader_id=user.id,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media, 0


@router.post("/check")
def check_hash(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """秒传检查：客户端算好 sha256 先来问，命中直接跳过上传。"""
    h = (payload or {}).get("content_hash", "")
    if not h:
        return {"exists": False, "item": None}
    media = db.scalar(select(Media).where(Media.content_hash == h))
    if media is None:
        return {"exists": False, "item": None}
    return {"exists": True, "item": to_out(media)}


def _transcode_bg(media_id: int, path_str: str):
    """后台视频转码：压到 720p 并更新库内大小。自开会话，独立于请求。"""
    from ..database import SessionLocal

    ok, new_size = transcode_to_720p(path_str)
    if ok:
        db = SessionLocal()
        try:
            m = db.get(Media, media_id)
            if m:
                m.size = new_size
                db.commit()
        finally:
            db.close()


def _normalize_audio_bg(media_id: int, path_str: str):
    """后台音频归一化：统一转 m4a AAC 并更新库内大小。自开会话，独立于请求。"""
    from ..database import SessionLocal

    ok, new_size = normalize_audio(path_str)
    if ok:
        db = SessionLocal()
        try:
            m = db.get(Media, media_id)
            if m:
                m.size = new_size
                # 归一化后容器已是 m4a，mime 同步修正保证浏览器播放行为正确
                if not m.mime_type.startswith("audio/"):
                    m.mime_type = "audio/mp4"
                db.commit()
        finally:
            db.close()


def _ai_tag_bg(media_id: int, path_str: str):
    """后台 AI 标记：qwen3-vl 生成标签与标题建议。失败静默（ai_tagged_at 空=可重试）。"""
    from ..database import SessionLocal

    try:
        result = tag_image(path_str)
    except Exception:
        return
    if not result:
        return
    db = SessionLocal()
    try:
        m = db.get(Media, media_id)
        if not m:
            return
        m.ai_caption = result["caption"]
        m.ai_tagged_at = datetime.now()
        for name in result["tags"]:
            tag = db.scalar(select(Tag).where(Tag.name == name))
            if not tag:
                tag = Tag(name=name)
                db.add(tag)
                db.flush()
            if tag not in m.tags:
                m.tags.append(tag)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@router.get("/tags/all")
def all_tags(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """全部标签及使用数（时间线筛选栏用）。"""
    rows = db.execute(
        select(Tag.id, Tag.name, func.count(media_tags.c.media_id))
        .join(media_tags, media_tags.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(func.count(media_tags.c.media_id).desc())
    ).all()
    return [{"id": r[0], "name": r[1], "count": r[2]} for r in rows]


@router.post("/ai/backfill")
def ai_backfill(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """存量补跑：给未标记的照片批量生成 AI 标记（同步，单次最多 20 张）。"""
    items = db.scalars(select(Media).where(Media.ai_tagged_at.is_(None)).limit(20)).all()
    processed = 0
    for m in items:
        path = Path(ORIGINALS_DIR) / m.filename
        if not path.exists():
            continue
        result = tag_image(path)
        if result:
            m.ai_caption = result["caption"]
            m.ai_tagged_at = datetime.now()
            for name in result["tags"]:
                tag = db.scalar(select(Tag).where(Tag.name == name))
                if not tag:
                    tag = Tag(name=name)
                    db.add(tag)
                    db.flush()
                if tag not in m.tags:
                    m.tags.append(tag)
            processed += 1
    db.commit()
    return {"processed": processed, "remaining": db.scalar(select(func.count()).select_from(select(Media).where(Media.ai_tagged_at.is_(None)).subquery())) or 0}


@router.post("/{media_id}/like")
def toggle_like(media_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """点赞/取消点赞（切换）。返回 {liked, likes}。"""
    media = db.get(Media, media_id)
    if not media:
        raise HTTPException(404, "媒体不存在")
    row = db.execute(
        select(media_likes).where(
            media_likes.c.media_id == media_id, media_likes.c.user_id == user.id
        )
    ).first()
    if row:
        db.execute(
            media_likes.delete().where(
                media_likes.c.media_id == media_id, media_likes.c.user_id == user.id
            )
        )
        media.likes_count = max(0, (media.likes_count or 0) - 1)
        liked = False
    else:
        db.execute(media_likes.insert().values(media_id=media_id, user_id=user.id))
        media.likes_count = (media.likes_count or 0) + 1
        liked = True
    db.commit()
    return {"liked": liked, "likes": media.likes_count}


@router.post("/{media_id}/ai/run")
def ai_run(media_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """单张即时生成 AI 标记（同步，约 10-30 秒）。"""
    media = db.get(Media, media_id)
    if not media:
        raise HTTPException(404, "媒体不存在")
    path = Path(ORIGINALS_DIR) / media.filename
    if not path.exists():
        raise HTTPException(404, "文件已丢失")
    if media.media_type != "photo":
        raise HTTPException(400, "音频/视频暂不支持 AI 标记")
    result = tag_image(path)
    if not result:
        raise HTTPException(502, "AI 服务无响应，请稍后重试")
    media.ai_caption = result["caption"]
    media.ai_tagged_at = datetime.now()
    for name in result["tags"]:
        tag = db.scalar(select(Tag).where(Tag.name == name))
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        if tag not in media.tags:
            media.tags.append(tag)
    db.commit()
    tags = [{"id": t.id, "name": t.name} for t in media.tags]
    return to_out(media, tags=tags)


@router.post("/{media_id}/adopt-caption")
def adopt_caption(media_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """一键采用：AI 建议标题覆盖人工图注（之后可继续编辑）。"""
    media = db.get(Media, media_id)
    if not media:
        raise HTTPException(404, "媒体不存在")
    if not media.ai_caption:
        raise HTTPException(400, "还没有 AI 标题建议")
    media.caption = media.ai_caption
    db.commit()
    return to_out(media)


@router.delete("/{media_id}/tags/{tag_id}")
def remove_tag(media_id: int, tag_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除一个标签（人工纠错）。"""
    media = db.get(Media, media_id)
    if not media:
        raise HTTPException(404, "媒体不存在")
    tag = db.get(Tag, tag_id)
    if tag and tag in media.tags:
        media.tags.remove(tag)
        db.commit()
    return {"ok": True}


@router.post("/upload/init")
def upload_init(total: int = Form(...), user: User = Depends(get_current_user)):
    if total < 1 or total > 10000:
        raise HTTPException(400, "非法分片数")
    upload_id = uuid.uuid4().hex
    d = os.path.join(TMP_DIR, upload_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "meta.json"), "w") as f:
        f.write(str(total))
    return {"upload_id": upload_id}


@router.post("/upload/{upload_id}/chunk")
async def upload_chunk(
    upload_id: str,
    index: int = Form(...),
    chunk: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    if not _valid_upload_id(upload_id):
        raise HTTPException(400, "非法 upload_id")
    d = os.path.join(TMP_DIR, upload_id)
    if not os.path.isdir(d):
        raise HTTPException(404, "上传会话不存在或已过期，请重新初始化")
    p = os.path.join(d, f"{index:06d}.part")
    with open(p, "wb") as out:
        while c := await chunk.read(1024 * 1024):
            out.write(c)
    received = len([f for f in os.listdir(d) if f.endswith(".part")])
    return {"received": received}


@router.get("/upload/{upload_id}/status")
def upload_status(upload_id: str, user: User = Depends(get_current_user)):
    if not _valid_upload_id(upload_id):
        raise HTTPException(400, "非法 upload_id")
    d = os.path.join(TMP_DIR, upload_id)
    if not os.path.isdir(d):
        return {"received": []}
    parts = sorted(int(f[:6]) for f in os.listdir(d) if f.endswith(".part"))
    return {"received": parts}


@router.post("/upload/{upload_id}/finalize")
async def upload_finalize(
    upload_id: str,
    orig_name: str = Form(...),
    taken_at_hint: str | None = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _valid_upload_id(upload_id):
        raise HTTPException(400, "非法 upload_id")
    d = os.path.join(TMP_DIR, upload_id)
    parts = sorted(Path(d).glob("*.part")) if os.path.isdir(d) else []
    if not parts:
        raise HTTPException(404, "没有已上传的分片")
    # 完整性校验：分片数必须与 init 声明的 total 一致
    meta_p = Path(d) / "meta.json"
    if meta_p.exists():
        try:
            total = int(meta_p.read_text().strip())
            if len(parts) != total:
                raise HTTPException(400, f"分片不完整: 已收 {len(parts)}/{total}")
        except ValueError:
            pass

    ext = os.path.splitext(orig_name)[1].lower()
    if ext not in ALLOWED_PHOTO_EXT and ext not in ALLOWED_VIDEO_EXT and ext not in ALLOWED_AUDIO_EXT:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(400, f"不支持的文件类型: {ext}")

    filename = uuid.uuid4().hex + ext
    dest = Path(ORIGINALS_DIR) / filename
    size = 0
    sha = hashlib.sha256()
    with open(dest, "wb") as out:
        for p in parts:
            with open(p, "rb") as f:
                while c := f.read(1024 * 1024):
                    size += len(c)
                    sha.update(c)
                    out.write(c)
    shutil.rmtree(d, ignore_errors=True)

    media, skipped = _process_final_file(dest, size, sha.hexdigest(), orig_name, taken_at_hint, user, db)
    if skipped:
        # 重复：丢弃刚拼好的文件，并告知与哪张重复
        try:
            dest.unlink(missing_ok=True)
        except OSError:
            pass
        dup = db.scalar(select(Media).where(Media.content_hash == sha.hexdigest()))
        return {"items": [], "skipped": 1, "existing": to_out(dup) if dup else None}
    if media.media_type == "video":
        background_tasks.add_task(_transcode_bg, media.id, str(dest))
    elif media.media_type == "audio":
        background_tasks.add_task(_normalize_audio_bg, media.id, str(dest))
    if media.media_type == "photo":
        background_tasks.add_task(_ai_tag_bg, media.id, str(dest))
    return {"items": [to_out(media)], "skipped": 0}


@router.get("")
def list_media(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    media_type: str | None = Query(None, pattern="^(photo|video|audio)$"),
    tag: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = select(Media)
    if media_type:
        q = q.where(Media.media_type == media_type)
    if tag:
        q = q.join(Media.tags).where(Tag.name == tag)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    items = db.scalars(
        q.order_by(Media.taken_at.desc(), Media.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    # 批量取评论数与标签（小红书风格卡片展示用）
    ids = [m.id for m in items]
    counts: dict[int, int] = {}
    if ids:
        rows = db.execute(
            select(Comment.target_id, func.count())
            .where(Comment.target_type == COMMENT_TARGET, Comment.target_id.in_(ids))
            .group_by(Comment.target_id)
        ).all()
        counts = {tid: n for tid, n in rows}
    tagmap = _batch_tags(db, ids)
    liked = set(
        db.execute(
            select(media_likes.c.media_id).where(
                media_likes.c.user_id == user.id, media_likes.c.media_id.in_(ids)
            )
        ).scalars().all()
    ) if ids else set()
    return {
        "total": total or 0,
        "page": page,
        "page_size": page_size,
        "items": [to_out(m, counts.get(m.id, 0), tagmap.get(m.id, []), m.id in liked) for m in items],
    }


@router.get("/{media_id}")
def get_media(media_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    media = db.get(Media, media_id)
    if not media:
        raise HTTPException(404, "媒体不存在")
    n = db.scalar(
        select(func.count()).select_from(
            select(Comment).where(Comment.target_type == COMMENT_TARGET, Comment.target_id == media_id).subquery()
        )
    )
    tags = [{"id": t.id, "name": t.name} for t in media.tags]
    liked = db.execute(
        select(media_likes.c.media_id).where(
            media_likes.c.user_id == user.id, media_likes.c.media_id == media_id
        )
    ).first() is not None
    return to_out(media, n or 0, tags, liked)


@router.patch("/{media_id}")
def update_media(
    media_id: int,
    data: MediaPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    media = db.get(Media, media_id)
    if not media:
        raise HTTPException(404, "媒体不存在")
    if data.caption is not None:
        media.caption = data.caption
    if data.taken_at is not None:
        media.taken_at = data.taken_at.replace(tzinfo=None)
        media.taken_at_source = "manual"
    db.commit()
    db.refresh(media)
    return to_out(media)


@router.delete("/{media_id}")
def delete_media(media_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    media = db.get(Media, media_id)
    if not media:
        raise HTTPException(404, "媒体不存在")
    # 删除关联评论与原始/缩略图文件
    for c in db.scalars(
        select(Comment).where(Comment.target_type == COMMENT_TARGET, Comment.target_id == media.id)
    ):
        db.delete(c)
    db.delete(media)
    db.commit()
    for base, name in ((ORIGINALS_DIR, media.filename), (THUMBS_DIR, media.thumb_filename)):
        if name:
            try:
                (Path(base) / name).unlink(missing_ok=True)
            except OSError:
                pass
    return {"ok": True}


@router.get("/{media_id}/file")
def get_file(media_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    media = db.get(Media, media_id)
    if not media:
        raise HTTPException(404, "媒体不存在")
    path = Path(ORIGINALS_DIR) / media.filename
    if not path.exists():
        raise HTTPException(404, "文件已丢失")
    return FileResponse(path, media_type=media.mime_type, filename=media.orig_name)


# ---- 媒体评论（嵌套便捷路由；通用路由见 comments.py）----

@router.get("/{media_id}/comments", response_model=list[CommentOut])
def list_media_comments(media_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not db.get(Media, media_id):
        raise HTTPException(404, "媒体不存在")
    items = db.scalars(
        select(Comment)
        .where(Comment.target_type == COMMENT_TARGET, Comment.target_id == media_id)
        .order_by(Comment.created_at.asc())
    ).all()
    return [_comment_out(c) for c in items]


@router.post("/{media_id}/comments", response_model=CommentOut)
def create_media_comment(
    media_id: int,
    data: CommentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not db.get(Media, media_id):
        raise HTTPException(404, "媒体不存在")
    comment = Comment(target_type=COMMENT_TARGET, target_id=media_id, author_id=user.id, body=data.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return _comment_out(comment)
