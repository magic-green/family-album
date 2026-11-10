"""拾光相册示例数据灌入脚本（幂等，全部内容为虚构）。

用法（在项目根目录执行）：

    python scripts/seed_demo.py

脚本会：
  * 用 Pillow 直接绘制若干张 640x480 的抽象卡通示例图（渐变背景 + 圆 / 云 / 花 /
    星等几何形状，不写任何文字以避开字体依赖），保存为 JPEG 到
    data/originals/ 与 data/thumbnails/；
  * 复用 backend/app 的 Base / engine / SessionLocal 建表，并插入 1 个虚构用户、
    1 条出生日期设置、若干条照片记录、几个中性标签与几条中性评论；
  * 所有 GPS / 设备 / 地点字段一律置空，不含任何真实个人信息、真实照片或 EXIF。

示例账号仅供本地演示，请勿在公网环境使用。跑完重启或刷新页面即可看到示例相册。
脚本可重复运行：已存在示例用户或示例媒体时直接跳过，不会重复插入。
只依赖 backend/requirements.txt 中已有的 Pillow、SQLAlchemy、bcrypt。
"""

import math
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

# 让 backend/app 可被导入
sys.path.insert(0, str(BACKEND))

# 把数据与数据库位置固定到项目根下，无论从哪个目录运行本脚本都一致。
# 用正斜杠形式，保证 SQLite 连接串在 Windows 上也是合法路径。
os.environ["DATA_DIR"] = (ROOT / "data").as_posix()
os.environ["DB_PATH"] = (ROOT / "db" / "app.db").as_posix()
# 以下两个只是占位值：仅用于满足配置模块在导入期的检查，
# 不参与真实认证，也不是任何真实密钥；若外部已设置则沿用外部值。
os.environ.setdefault("INVITE_CODE", "seed-demo-local-only")
os.environ.setdefault("JWT_SECRET", "seed-demo-local-only-placeholder")

import bcrypt
from PIL import Image, ImageDraw

from app import config as app_config
from app.database import Base, SessionLocal, engine
from app.models import Comment, Media, Setting, Tag, User, media_tags

ORIGINALS = Path(app_config.ORIGINALS_DIR)
THUMBS = Path(app_config.THUMBS_DIR)
DB_FILE = Path(app_config.DB_PATH)

WIDTH, HEIGHT = 640, 480
THUMB_WIDTH = 320
OUTLINE = (122, 91, 69)

DEMO_USER = "demo"
DEMO_PASSWORD = "demo1234"  # 仅本地演示用，明文写死便于体验，请勿用于公网
BIRTH_DATE = "2024-01-01"

# 虚构的示例照片：中性短句图注 + 相对基准日期的天数偏移（都不是真实事件）
DEMO_PHOTOS = [
    ("阳光正好", -120),
    ("云朵和风", -96),
    ("小花开了", -72),
    ("小鸭戏水", -54),
    ("彩色气球", -33),
    ("夜晚的星星", -18),
    ("雨后的彩虹", -7),
    ("按下快门", -1),
]

DEMO_TAGS = ["户外", "晴天", "小物件"]  # 中性标签，不含人物 / 地点信息
DEMO_COMMENTS = ["这张颜色真好看。", "收藏起来啦。"]

BASE_DATE = datetime(2024, 6, 1, 10, 0)  # 虚构基准日期

# 奶油 / 蜜桃 / 蜂蜜色系：背景渐变上下色 + 主体大圆的点缀色
PALETTES = [
    ((255, 247, 232), (255, 226, 198), (255, 211, 110)),
    ((255, 248, 237), (226, 240, 248), (175, 214, 238)),
    ((255, 246, 232), (255, 229, 210), (255, 183, 160)),
    ((255, 249, 238), (232, 244, 226), (190, 226, 198)),
    ((255, 246, 238), (246, 232, 250), (217, 199, 240)),
    ((255, 245, 230), (255, 220, 196), (249, 190, 122)),
    ((255, 249, 240), (233, 243, 250), (175, 214, 238)),
    ((255, 246, 234), (255, 227, 205), (255, 211, 110)),
]


def _star_points(cx, cy, radius):
    pts = []
    for k in range(10):
        ang = -math.pi / 2 + k * math.pi / 5
        r = radius if k % 2 == 0 else radius * 0.45
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def make_image(index):
    """纯代码绘制一张抽象卡通图：渐变背景 + 圆 / 云 / 星 / 花，不含任何文字。"""
    top, bottom, accent = PALETTES[index % len(PALETTES)]
    img = Image.new("RGB", (WIDTH, HEIGHT))
    d = ImageDraw.Draw(img)

    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        color = tuple(int(top[c] + (bottom[c] - top[c]) * t) for c in range(3))
        d.line([(0, y), (WIDTH, y)], fill=color)

    band = tuple(min(255, int(c * 0.94 + 8)) for c in bottom)
    d.rectangle([0, 398, WIDTH, HEIGHT], fill=band)

    # 主体大圆（太阳 / 气球 / 花心之类的抽象点缀）
    ox = 70 + (index % 3) * 62
    oy = 96 + (index % 2) * 34
    d.ellipse([ox, oy, ox + 148, oy + 148], fill=accent, outline=OUTLINE, width=4)
    d.ellipse([ox + 26, oy + 24, ox + 62, oy + 60], fill=(255, 255, 255))

    # 云朵：三个叠圆 + 一条平底
    cy = 236 + (index % 3) * 18
    for cx, r in ((300, 40), (350, 54), (404, 38)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255),
                  outline=OUTLINE, width=3)
    d.rectangle([300, cy, 404, cy + 38], fill=(255, 255, 255),
                outline=OUTLINE, width=3)

    # 星星
    for k in range(4):
        sx = 90 + k * 138 + (index * 17) % 56
        sy = 62 + (k % 2) * 58
        d.polygon(_star_points(sx, sy, 17), fill=(255, 216, 130), outline=OUTLINE)

    # 小花：五片花瓣围绕花心
    fx, fy = 512, 312
    for k in range(5):
        ang = k * 2 * math.pi / 5
        px = fx + 26 * math.cos(ang)
        py = fy + 26 * math.sin(ang)
        d.ellipse([px - 14, py - 14, px + 14, py + 14],
                  fill=(255, 183, 160), outline=OUTLINE, width=2)
    d.ellipse([fx - 12, fy - 12, fx + 12, fy + 12],
              fill=(255, 211, 110), outline=OUTLINE, width=2)

    return img


def already_seeded(db):
    if db.query(User).filter(User.username == DEMO_USER).first() is not None:
        return True
    if db.query(Media).filter(Media.orig_name.like("sample_%")).first() is not None:
        return True
    return False


def main():
    ORIGINALS.mkdir(parents=True, exist_ok=True)
    THUMBS.mkdir(parents=True, exist_ok=True)
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if already_seeded(db):
            print("示例数据已存在，跳过（脚本可重复运行，不会重复插入）。")
            return

        user = User(
            username=DEMO_USER,
            password_hash=bcrypt.hashpw(
                DEMO_PASSWORD.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8"),
        )
        db.add(user)
        db.flush()

        if db.get(Setting, "birth_date") is None:
            db.add(Setting(key="birth_date", value=BIRTH_DATE))

        tag_objs = []
        for name in DEMO_TAGS:
            tag = db.query(Tag).filter(Tag.name == name).first()
            if tag is None:
                tag = Tag(name=name)
                db.add(tag)
                db.flush()
            tag_objs.append(tag)

        media_ids = []
        for i, (caption, offset) in enumerate(DEMO_PHOTOS):
            filename = f"{uuid.uuid4().hex}.jpg"
            img = make_image(i)
            orig_path = ORIGINALS / filename
            img.save(orig_path, format="JPEG", quality=88)
            thumb = img.resize(
                (THUMB_WIDTH, round(HEIGHT * THUMB_WIDTH / WIDTH)), Image.LANCZOS
            )
            thumb.save(THUMBS / filename, format="JPEG", quality=82)

            media = Media(
                filename=filename,
                thumb_filename=filename,
                orig_name=f"sample_{i + 1:02d}.jpg",
                media_type="photo",
                mime_type="image/jpeg",
                size=orig_path.stat().st_size,
                caption=caption,
                taken_at=BASE_DATE + timedelta(days=offset),
                taken_at_source="upload",
                camera_make=None,
                camera_model=None,
                gps_lat=None,
                gps_lon=None,
                location_name=None,
                content_hash=None,
                width=WIDTH,
                height=HEIGHT,
                uploader_id=user.id,
            )
            db.add(media)
            db.flush()
            media_ids.append(media.id)

            for tag in tag_objs[:2]:
                db.execute(
                    media_tags.insert().values(
                        media_id=media.id, tag_id=tag.id, source="manual"
                    )
                )

        for i, body in enumerate(DEMO_COMMENTS):
            db.add(Comment(
                target_type="media",
                target_id=media_ids[i % len(media_ids)],
                author_id=user.id,
                body=body,
            ))

        db.commit()
        print(
            f"完成：写入 {len(DEMO_PHOTOS)} 张示例图、{len(DEMO_TAGS)} 个标签、"
            f"{len(DEMO_COMMENTS)} 条评论，出生日期已设为 {BIRTH_DATE}。"
        )
        print(f"示例账号：{DEMO_USER} / {DEMO_PASSWORD}（仅本地演示用，请勿用于公网）")
        print("重启或刷新页面即可看到示例相册。")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
