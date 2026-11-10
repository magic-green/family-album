"""音频后处理：上传完成后后台归一化为 m4a AAC，统一格式并压缩。

设计要点（与 videos.py 对齐）：
- 转码在后台任务跑（上传接口已先返回），不阻塞响应
- 先写 .norm.m4a 临时文件，成功后原子替换原文件
- 归一化目标：AAC 96k（语音/儿歌足够），容器统一 m4a
- 转出来比原来还大（如本来就是小 m4a）就不替换，保留原文件
"""

import os
import shutil
import subprocess
from pathlib import Path


def _ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def normalize_audio(path: str | Path) -> tuple[bool, int]:
    """任意音频 → m4a AAC 96k 并原子替换。返回 (是否替换, 生效字节数)。"""
    ffmpeg = _ffmpeg()
    if not ffmpeg:
        return False, 0
    path = Path(path)
    if not path.exists():
        return False, 0
    tmp = path.with_suffix(".norm.m4a")
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", str(path),
        "-vn",  # 掐掉可能的封面流，纯音频
        "-c:a", "aac", "-b:a", "96k",
        # .m4a 原文件转出来同名容器：faststart 对纯音频无影响但无害
        "-movflags", "+faststart",
        str(tmp),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=600, capture_output=True)
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
