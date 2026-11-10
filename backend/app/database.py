from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_columns():
    """轻量迁移：media 表缺列时用 ALTER TABLE 补齐（SQLite 支持加列）。

    全新库（无表）时跳过，交给 create_all 建全量表。
    """
    from sqlalchemy import text

    new_cols = {
        "camera_make": "VARCHAR(64)",
        "camera_model": "VARCHAR(64)",
        "gps_lat": "FLOAT",
        "gps_lon": "FLOAT",
        "location_name": "VARCHAR(255)",
        "content_hash": "VARCHAR(64)",
        "width": "INTEGER",
        "height": "INTEGER",
        "ai_caption": "TEXT",
        "ai_tagged_at": "DATETIME",
        "likes_count": "INTEGER DEFAULT 0",
    }
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(media)")).fetchall()
        if not rows:
            return
        existing = {r[1] for r in rows}
        for col, ddl in new_cols.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE media ADD COLUMN {col} {ddl}"))
        conn.commit()
