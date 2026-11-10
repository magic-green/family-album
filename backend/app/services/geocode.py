"""可选逆地理编码：GPS 坐标 → 中文地名。

需自行配置 AMAP_KEY；未配置或调用失败时返回 None（前端降级显示坐标）。
短连接小响应，失败静默降级，不阻塞上传主流程。
"""

import json
import os
import urllib.request


def reverse_geocode(lat: float, lon: float, timeout: float = 3.0) -> str | None:
    key = (os.getenv("AMAP_KEY") or "").strip()
    if not key:
        return None
    # 高德要求 lon,lat 顺序
    url = (
        "https://restapi.amap.com/v3/geocode/regeo"
        f"?key={key}&location={lon:.6f},{lat:.6f}&extensions=base"
    )
    try:
        # 直连，不继承环境代理
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == "1" and data.get("regeocode"):
            addr = data["regeocode"].get("formatted_address")
            return addr or None
    except Exception:
        return None
    return None
