import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import ensure_dirs, ORIGINALS_DIR, THUMBS_DIR, AVATARS_DIR
from .database import Base, engine, ensure_columns
from .routers import auth_router, media, comments, albums

ensure_dirs()
Base.metadata.create_all(bind=engine)
ensure_columns()


def _backfill_dimensions():
    """老数据补宽高（瀑布流布局用），只在缺时有动作。"""
    import os

    from sqlalchemy import select

    from .database import SessionLocal
    from .models import Media
    from .services.thumbnails import get_dimensions

    db = SessionLocal()
    try:
        rows = db.scalars(select(Media).where(Media.width.is_(None))).all()
        for m in rows:
            dims = None
            if m.media_type == "photo":
                dims = get_dimensions(os.path.join(ORIGINALS_DIR, m.filename))
            if dims is None and m.thumb_filename:
                dims = get_dimensions(os.path.join(THUMBS_DIR, m.thumb_filename))
            if dims:
                m.width, m.height = dims
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


_backfill_dimensions()

app = FastAPI(title="Family Album API", version="0.1.0")

_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8020").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(media.router)
app.include_router(comments.router)
app.include_router(albums.album_router)
app.include_router(albums.tag_router)

from .routers import system as system_router  # noqa: E402

app.include_router(system_router.router)

# 静态文件：原图与缩略图
app.mount("/data/originals", StaticFiles(directory=ORIGINALS_DIR), name="originals")
app.mount("/data/thumbnails", StaticFiles(directory=THUMBS_DIR), name="thumbnails")
app.mount("/data/avatars", StaticFiles(directory=AVATARS_DIR), name="avatars")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---- 前端静态托管（可选）：STATIC_DIR 存在时同源托管 dist，SPA fallback 到 index.html ----
STATIC_DIR = os.getenv("STATIC_DIR", "static")
_index_html = os.path.join(STATIC_DIR, "index.html")
if os.path.isfile(_index_html):
    _assets_dir = os.path.join(STATIC_DIR, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        candidate = os.path.join(STATIC_DIR, full_path)
        # 防路径穿越：解析后必须仍在 STATIC_DIR 内
        if full_path and os.path.realpath(candidate).startswith(os.path.realpath(STATIC_DIR)) and os.path.isfile(candidate):
            # 指纹静态资源可长缓存；index.html 等入口必须每次校验，避免更新后浏览器拿旧页面
            if full_path.startswith("assets/"):
                return FileResponse(candidate, headers={"Cache-Control": "public, max-age=31536000, immutable"})
            return FileResponse(candidate, headers={"Cache-Control": "no-cache"})
        return FileResponse(_index_html, headers={"Cache-Control": "no-cache"})
