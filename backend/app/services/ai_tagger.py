"""AI 标记：调用视觉大模型为图片生成通用标签与简短标题。

- 模型服务地址可通过 OLLAMA_URL 配置，未部署时 AI 功能自动降级（失败返回 None）
- 强制 JSON 输出；失败返回 None（ai_tagged_at 保持空，可重试）
- keep_alive=5m：不常驻显存，与视频转码错峰
"""

import base64
import json
import os
import re
import urllib.request

# 用 or 而非 getenv 默认值：compose 里 ${VAR:-} 会注入空字符串，
# 空值同样应回退到示例默认，避免 AI 功能异常而非优雅降级。
OLLAMA_URL = os.getenv("OLLAMA_URL") or "http://localhost:11434"
MODEL = os.getenv("AI_TAG_MODEL") or "qwen3-vl:4b"  # 示例值，可按实际部署的模型覆盖

PROMPT = """你是通用相册的 AI 助手。请为这张图片生成 3 到 6 个通用标签与一句简短标题。
标签规则（严格遵守）：
- 标签取自中性的场景、活动、物体、季节、天气等类别，如 户外、旅行、聚会、美食、花卉、建筑、雪景、夜景、运动、阅读
- 只描述画面客观内容，不要推测人物身份、关系、年龄或性别
- 每个标签 2 到 4 个汉字，避免使用无信息量的泛词
输出 JSON（不要输出其他内容）：
{"tags": ["标签1", "标签2"], "caption": "一句 20 字以内的简短标题"}"""

# 服务端兜底黑名单：模型不听话时过滤无信息量的泛词
TAG_BLACKLIST = {
    "日常", "生活", "随手拍", "记录", "照片", "图片", "温馨", "萌", "好看", "精彩",
}

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _clean_think(text: str) -> str:
    # 部分模型会带思考段，剥离
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def _downscale(path) -> bytes | None:
    """缩到长边 1024 再喂模型（视觉编码快 2-3 倍），失败返回 None 用原图。"""
    try:
        import io

        from PIL import Image

        with Image.open(path) as img:
            img = img.convert("RGB")
            scale = min(1.0, 1024 / max(img.width, img.height))
            if scale < 1.0:
                img = img.resize((int(img.width * scale), int(img.height * scale)))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue()
    except Exception:
        return None


def tag_image(path) -> dict | None:
    """分析图片，返回 {tags:[...], caption:str|None}；失败返回 None。"""
    try:
        data_bytes = _downscale(path)
        if data_bytes is None:
            with open(path, "rb") as f:
                data_bytes = f.read()
        b64 = base64.b64encode(data_bytes).decode()
        body = {
            "model": MODEL,
            "prompt": PROMPT,
            "images": [b64],
            "stream": False,
            "format": "json",
            "keep_alive": "5m",
            "options": {"temperature": 0.3, "num_predict": 300},
        }
        req = urllib.request.Request(
            OLLAMA_URL + "/api/generate",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with _opener.open(req, timeout=180) as resp:
            data = json.loads(resp.read().decode())
        text = _clean_think(data.get("response", ""))
        parsed = json.loads(text)
        tags = []
        for t in parsed.get("tags", []):
            t = str(t).strip().strip("#")
            if t in TAG_BLACKLIST:
                continue
            if 1 <= len(t) <= 8 and t not in tags:
                tags.append(t)
            if len(tags) >= 6:
                break
        caption = str(parsed.get("caption", "")).strip()[:60] or None
        if not tags and not caption:
            return None
        return {"tags": tags, "caption": caption}
    except Exception:
        return None
