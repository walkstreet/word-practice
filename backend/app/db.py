from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


def _sqlite_connect_args(url: str) -> dict:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


Base = declarative_base()
VocabBase = declarative_base()

engine = create_engine(
    settings.database_url,
    connect_args=_sqlite_connect_args(settings.database_url),
)
vocab_engine = create_engine(
    settings.vocabulary_database_url,
    connect_args=_sqlite_connect_args(settings.vocabulary_database_url),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
VocabSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=vocab_engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_vocab_db():
    db = VocabSessionLocal()
    try:
        yield db
    finally:
        db.close()
