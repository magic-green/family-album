"""媒体元数据提取：拍摄时间（EXIF/文件名/mtime）、设备、GPS。

时间恢复优先级（微信另存图无 EXIF，靠文件名兜底）：
  EXIF DateTimeOriginal > 文件名时间戳 > 批次提示(调用方处理) > 文件 mtime > 上传时间
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass

TAG_DATETIME_ORIGINAL = 0x9003
TAG_DATETIME = 0x0132
TAG_MAKE = 0x010F
TAG_MODEL = 0x0110
IFD_EXIF = 0x8769
IFD_GPS = 0x8825


def _clean(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    value = str(value).strip().strip("\x00").strip()
    return value or None


def _get_datetime(exif) -> str | None:
    # 1) Exif IFD 里的 DateTimeOriginal
    try:
        ifd = exif.get_ifd(IFD_EXIF)
        if ifd:
            v = _clean(ifd.get(TAG_DATETIME_ORIGINAL))
            if v:
                return v
    except Exception:
        pass
    # 2) 基础 IFD 的 DateTimeOriginal（部分写法）
    v = _clean(exif.get(TAG_DATETIME_ORIGINAL))
    if v:
        return v
    # 3) 基础 IFD 的 DateTime
    return _clean(exif.get(TAG_DATETIME))


def _parse_exif_datetime(value: str) -> datetime | None:
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


# ---- 文件名时间戳（微信/截图/相册导出场景） ----

# (pattern, handler)  handler: match -> datetime | None
_FILENAME_PATTERNS = [
    # 微信导出/聊天相机：秒或毫秒时间戳，如 mmexport1698765432.jpg、wx_camera_1698765432100.jpg
    (
        re.compile(r"(?:mmexport|mmcrop|wx_camera|VideoChat)(\d{10,13})", re.I),
        lambda m: _unix(m.group(1)),
    ),
    # 相机命名：IMG_20250315_123456 / VID_20250315_123456 / DSC-20250315-123456
    (
        re.compile(r"(?:IMG|VID|DSC|PXL|MVIMG)[-_]?(\d{8})[-_](\d{6})", re.I),
        lambda m: _digits(m.group(1), m.group(2)),
    ),
    # WhatsApp：IMG-20250315-WA0001（仅日期）
    (
        re.compile(r"IMG-(\d{8})-WA\d+", re.I),
        lambda m: _digits(m.group(1)),
    ),
    # 截图：Screenshot_2025-03-15-12-34-56 / Screenshot_20250315-123456 / 屏幕截图 2025-03-15 123456
    (
        re.compile(r"(?:Screenshot|屏幕截图|Screenshot_)[^\d]{0,3}(\d{4})[-_年]?(\d{2})[-_月]?(\d{2})[^\d]+(\d{2})[-_分时]?(\d{2})[-_]?(\d{2})?", re.I),
        lambda m: _ymd(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)),
    ),
    # 纯数字文件名：1698765432100.jpg（毫秒）/ 1698765432.jpg（秒）
    (
        re.compile(r"^(\d{13})(?:\.\w+)?$"),
        lambda m: _unix(m.group(1)),
    ),
    (
        re.compile(r"^(\d{10})(?:\.\w+)?$"),
        lambda m: _unix(m.group(1)),
    ),
]


def _unix(digits: str) -> datetime | None:
    try:
        v = int(digits)
        if v > 10**12:  # 毫秒
            v //= 1000
        if not (10**9 < v < 2 * 10**9):  # 2001~2033 之间才可信
            return None
        # 微信时间戳是用户本地（按北京时间）生成，按东八区解读避免日期跨天
        cst = timezone(timedelta(hours=8))
        return datetime.fromtimestamp(v, tz=cst).replace(tzinfo=None)
    except (ValueError, OSError, OverflowError):
        return None


def _digits(date8: str, time6: str | None = None) -> datetime | None:
    try:
        d = datetime.strptime(date8, "%Y%m%d")
        if time6:
            d = datetime.strptime(date8 + time6, "%Y%m%d%H%M%S")
        return d
    except ValueError:
        return None


def _ymd(y, mo, d, h="0", mi="0", s="0") -> datetime | None:
    try:
        return datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), int(s or 0))
    except ValueError:
        return None


def parse_filename_datetime(name: str) -> datetime | None:
    """从文件名解析拍摄/导出时间，解析不出返回 None。"""
    for pattern, handler in _FILENAME_PATTERNS:
        m = pattern.search(name)
        if m:
            dt = handler(m)
            if dt:
                return dt
    return None


# ---- EXIF 设备与 GPS ----


def _dms_to_deg(value) -> float | None:
    """EXIF 的 DMS 度分秒 → 十进制度。"""
    try:
        dms = [float(v) for v in value] if not hasattr(value, "numerator") else [float(value)]
        if len(dms) == 3:
            return dms[0] + dms[1] / 60 + dms[2] / 3600
        if len(dms) == 2:
            return dms[0] + dms[1] / 60
        if len(dms) == 1:
            return dms[0]
    except Exception:
        pass
    return None


def _get_gps(exif) -> tuple[float, float] | None:
    try:
        gps = exif.get_ifd(IFD_GPS)
        if not gps:
            return None
        lat = _dms_to_deg(gps.get(2))
        lon = _dms_to_deg(gps.get(4))
        if lat is None or lon is None:
            return None
        lat_ref = (_clean(gps.get(1)) or "N").upper()
        lon_ref = (_clean(gps.get(3)) or "E").upper()
        if lat_ref == "S":
            lat = -lat
        if lon_ref == "W":
            lon = -lon
        if abs(lat) > 90 or abs(lon) > 180 or (lat == 0 and lon == 0):
            return None
        return round(lat, 6), round(lon, 6)
    except Exception:
        return None


def extract_metadata(path: str | Path, orig_name: str | None = None) -> dict:
    """提取全部可用元数据。

    返回 {taken_at, taken_at_source, camera_make, camera_model, gps_lat, gps_lon}
    source: exif / filename / file_mtime / upload
    """
    path = Path(path)
    result = {
        "taken_at": None,
        "taken_at_source": None,
        "camera_make": None,
        "camera_model": None,
        "gps_lat": None,
        "gps_lon": None,
    }

    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if exif:
                raw = _get_datetime(exif)
                if raw:
                    dt = _parse_exif_datetime(raw)
                    if dt:
                        result["taken_at"] = dt
                        result["taken_at_source"] = "exif"
                result["camera_make"] = _clean(exif.get(TAG_MAKE))
                result["camera_model"] = _clean(exif.get(TAG_MODEL))
                gps = _get_gps(exif)
                if gps:
                    result["gps_lat"], result["gps_lon"] = gps
    except Exception:
        pass  # 视频或无 EXIF 文件

    # 文件名兜底（微信另存图的主路径）
    if result["taken_at"] is None:
        name = orig_name or path.name
        dt = parse_filename_datetime(name)
        if dt:
            result["taken_at"] = dt
            result["taken_at_source"] = "filename"

    # 文件 mtime 兜底
    if result["taken_at"] is None:
        try:
            result["taken_at"] = datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).replace(tzinfo=None)
            result["taken_at_source"] = "file_mtime"
        except OSError:
            result["taken_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
            result["taken_at_source"] = "upload"

    return result


def parse_hint_datetime(hint: str) -> datetime | None:
    """解析用户提供的批次日期提示：2025 / 2025-03 / 2025-03-15 / ISO 日期时间。"""
    hint = (hint or "").strip()
    if not hint:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y年%m月%d日",
        "%Y-%m",
        "%Y年%m月",
        "%Y",
    ):
        try:
            return datetime.strptime(hint, fmt)
        except ValueError:
            continue
    return None


def extract_taken_at(path: str | Path) -> tuple[datetime, str]:
    """向后兼容：仅返回 (taken_at, source)。source: exif / filename / file_mtime / upload。"""
    meta = extract_metadata(path)
    return meta["taken_at"], meta["taken_at_source"]
