"""运行配置与凭证策略。

凭证约定：
- INVITE_CODE 必须由环境变量提供，未设置时启动即报错，不提供弱默认值。
- JWT_SECRET 优先取环境变量；未设置时自动生成随机密钥并持久化到 db/.jwt_secret，
  保证进程重启后已签发的 token 仍然有效。
"""

import os
import secrets
import shutil
from pathlib import Path

# ---- 认证配置 ----
_invite_code = os.getenv("INVITE_CODE")
if not _invite_code:
    raise RuntimeError("缺少 INVITE_CODE：请在 .env 中设置 INVITE_CODE 后重新启动")
INVITE_CODE = _invite_code


def _load_jwt_secret() -> str:
    env_secret = os.getenv("JWT_SECRET")
    if env_secret:
        return env_secret
    # 与 DB_PATH 同目录，避免本地直跑时密钥与数据库分离、或误写进源码目录
    db_path = os.getenv("DB_PATH", os.path.join("db", "app.db"))
    secret_file = Path(db_path).parent / ".jwt_secret"
    if secret_file.is_file():
        saved = secret_file.read_text(encoding="utf-8").strip()
        if saved:
            return saved
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_urlsafe(48)
    secret_file.write_text(secret, encoding="utf-8")
    try:
        os.chmod(secret_file, 0o600)
    except OSError:
        pass
    return secret


JWT_SECRET = _load_jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = int(os.getenv("JWT_EXPIRE_DAYS") or 30)

# ---- 数据目录（相对于 backend 运行目录）----
DATA_DIR = os.getenv("DATA_DIR", "data")
ORIGINALS_DIR = os.path.join(DATA_DIR, "originals")
THUMBS_DIR = os.path.join(DATA_DIR, "thumbnails")
TMP_DIR = os.path.join(DATA_DIR, "tmp")  # 分片上传暂存
AVATARS_DIR = os.path.join(DATA_DIR, "avatars")  # 自定义头像
DB_PATH = os.getenv("DB_PATH", os.path.join("db", "app.db"))

# ---- 上传限制 ----
ALLOWED_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".m4v"}
ALLOWED_AUDIO_EXT = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".amr", ".flac", ".3gp"}

THUMB_WIDTH = 640


def ensure_dirs():
    for d in (ORIGINALS_DIR, THUMBS_DIR, TMP_DIR, AVATARS_DIR, os.path.dirname(DB_PATH) or "."):
        os.makedirs(d, exist_ok=True)
    # 清理超过 24 小时的分片上传残留
    import time

    now = time.time()
    try:
        for name in os.listdir(TMP_DIR):
            p = os.path.join(TMP_DIR, name)
            if os.path.isdir(p) and now - os.path.getmtime(p) > 86400:
                shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass
