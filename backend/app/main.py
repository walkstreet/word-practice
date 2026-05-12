from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.db import Base, engine
from app.routers import auth, practice, stats, vocab, wrongbook


Base.metadata.create_all(bind=engine)


def ensure_vocabulary_columns():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(vocabulary)")).fetchall()}
        if "phonetic" not in columns:
            conn.execute(text("ALTER TABLE vocabulary ADD COLUMN phonetic VARCHAR(128) NOT NULL DEFAULT ''"))
        if "part_of_speech" not in columns:
            conn.execute(
                text("ALTER TABLE vocabulary ADD COLUMN part_of_speech VARCHAR(64) NOT NULL DEFAULT ''")
            )
        if "senses" not in columns:
            conn.execute(text("ALTER TABLE vocabulary ADD COLUMN senses JSON"))


ensure_vocabulary_columns()


def sync_vocabulary_normalized_words():
    """用与导入相同的 Python 规则统一 word / normalized_word，避免历史 SQL TRIM 与 NFKC strip 不一致。"""
    from app.db import SessionLocal
    from app.models import Vocabulary
    from app.services.masking import normalize_word as canon_word

    db = SessionLocal()
    try:
        for row in db.query(Vocabulary).all():
            w = canon_word(row.word)
            if row.word != w:
                row.word = w
            if row.normalized_word != w:
                row.normalized_word = w
        db.commit()
    finally:
        db.close()


sync_vocabulary_normalized_words()


def prune_non_admin_users():
    """个人使用：若库中有用户名为 admin 的账号，删除其余用户及其练习、错题数据。"""
    from app.db import SessionLocal
    from app.models import PracticeRecord, User, WrongBook

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if admin is None:
            return
        other_ids = [uid for (uid,) in db.query(User.id).filter(User.id != admin.id).all()]
        if not other_ids:
            return
        db.query(PracticeRecord).filter(PracticeRecord.user_id.in_(other_ids)).delete(synchronize_session=False)
        db.query(WrongBook).filter(WrongBook.user_id.in_(other_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(other_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


if settings.prune_non_admin_users_on_startup:
    prune_non_admin_users()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_origin_regex=(settings.cors_allow_origin_regex.strip() or None),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_api = settings.api_prefix
app.include_router(auth.router, prefix=_api)
app.include_router(vocab.router, prefix=_api)
app.include_router(practice.router, prefix=_api)
app.include_router(wrongbook.router, prefix=_api)
app.include_router(stats.router, prefix=_api)


@app.get("/health")
def health():
    out: dict = {"status": "ok"}
    url = settings.database_url
    if url.startswith("sqlite:///"):
        out["sqlite_path"] = url.replace("sqlite:///", "")
    return out
