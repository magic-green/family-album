"""视频后处理：上传完成后后台转 720p H.264，节省存储与播放流量。

设计要点：
- 转码在后台任务跑（finalize 已先返回），不阻塞上传响应
- 先写 .transcode.mp4 临时文件，成功后原子替换原文件
- 转出来比原来还大（低分辨率原片）就不替换
"""

import os
import shutil
import subprocess
from pathlib import Path

from ..config import ORIGINALS_DIR


def _ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def transcode_to_720p(path: str | Path) -> tuple[bool, int]:
    """720p H.264 CRF28 转码并原子替换。返回 (是否替换, 生效字节数)。"""
    ffmpeg = _ffmpeg()
    if not ffmpeg:
        return False, 0
    path = Path(path)
    if not path.exists():
        return False, 0
    tmp = path.with_suffix(".transcode.mp4")
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", str(path),
        "-vf", "scale=-2:720",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        str(tmp),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=1800, capture_output=True)
        if tmp.exists() and tmp.stat().st_size > 0:
            new_size = tmp.stat().st_size
            if new_size < path.stat().st_size:
                os.replace(tmp, path)
                return True, new_size
            tmp.unlink(missing_ok=True)
            return False, path.stat().st_size
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    return False, 0
