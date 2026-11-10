"""缩略图生成：图片用 Pillow，视频用 ffmpeg 截首帧。"""

import shutil
import subprocess
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..config import THUMBS_DIR, THUMB_WIDTH


def _save_resized(img: Image.Image, out_path: Path) -> None:
    img = img.convert("RGB")
    if img.width > THUMB_WIDTH:
        ratio = THUMB_WIDTH / img.width
        img = img.resize((THUMB_WIDTH, max(1, int(img.height * ratio))), Image.LANCZOS)
    img.save(out_path, "JPEG", quality=85)


def image_thumbnail(src: str | Path) -> str | None:
    """生成图片缩略图，返回缩略图文件名。"""
    src = Path(src)
    name = f"{uuid.uuid4().hex}.jpg"
    out = Path(THUMBS_DIR) / name
    try:
        with Image.open(src) as img:
            _save_resized(img, out)
        return name
    except Exception:
        return None


def _resolve_ffmpeg() -> str | None:
    """优先 PATH 里的 ffmpeg，没有则回退 imageio-ffmpeg 自带的静态二进制。"""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return get_ffmpeg_exe()
    except Exception:
        return None


def video_thumbnail(src: str | Path) -> str | None:
    """用 ffmpeg 截视频首帧生成缩略图，返回缩略图文件名。"""
    ffmpeg = _resolve_ffmpeg()
    if not ffmpeg:
        return None
    src = Path(src)
    name = f"{uuid.uuid4().hex}.jpg"
    out = Path(THUMBS_DIR) / name
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", str(src),
        "-vframes", "1",
        "-vf", f"scale={THUMB_WIDTH}:-2",
        "-q:v", "3",
        str(out),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=60, capture_output=True)
        if out.exists() and out.stat().st_size > 0:
            return name
    except Exception:
        pass
    return None


def audio_thumbnail(src: str | Path) -> str | None:
    """音频无画面：生成音符占位卡（奶油底 + ♪），返回缩略图文件名。"""
    name = f"{uuid.uuid4().hex}.jpg"
    out = Path(THUMBS_DIR) / name
    try:
        size = THUMB_WIDTH
        img = Image.new("RGB", (size, size), (253, 246, 227))  # 奶油底（cream）
        draw = ImageDraw.Draw(img)
        # 底部浅色圆弧装饰
        draw.ellipse(
            (-size * 0.3, size * 0.55, size * 1.3, size * 1.6),
            fill=(252, 231, 186),
        )
        # 中央音符：跨平台挑选支持 ♪ 的字体，均不可用时回退 Pillow 默认字体
        glyph = "♪♪"
        font = None
        for font_path in (
            # Windows
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/seguisb.ttf",
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            # macOS
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
        ):
            try:
                font = ImageFont.truetype(font_path, int(size * 0.32))
                break
            except OSError:
                continue
        if font is None:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), glyph, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
            glyph,
            font=font,
            fill=(214, 149, 81),  # honey 深色
        )
        img.save(out, "JPEG", quality=85)
        return name
    except Exception:
        return None


def get_dimensions(path: str | Path) -> tuple[int, int] | None:
    """取图片宽高（视频传缩略图路径即可，宽高比一致）。失败返回 None。"""
    try:
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:
        return None


def make_thumbnail(src: str | Path, media_type: str) -> str | None:
    if media_type == "video":
        return video_thumbnail(src)
    if media_type == "audio":
        return audio_thumbnail(src)
    return image_thumbnail(src)
