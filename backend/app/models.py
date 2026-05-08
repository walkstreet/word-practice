from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db import Base, VocabBase


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Vocabulary(VocabBase):
    __tablename__ = "vocabulary"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(128), nullable=False)
    translation = Column(Text, nullable=False)
    phonetic = Column(String(128), nullable=False, default="")
    part_of_speech = Column(String(512), nullable=False, default="")
    senses = Column(JSON, nullable=True)
    normalized_word = Column(String(128), unique=True, index=True, nullable=False)
    source = Column(String(64), default="import", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PracticeRecord(Base):
    __tablename__ = "practice_record"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    vocabulary_id = Column(Integer, index=True, nullable=False)
    question_mask = Column(String(255), nullable=False)
    missing_positions = Column(JSON, nullable=False)
    user_answer = Column(String(128), nullable=False)
    correct_answer = Column(String(128), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")


class WrongBook(Base):
    __tablename__ = "wrong_book"
    __table_args__ = (UniqueConstraint("user_id", "vocabulary_id", name="uq_user_vocabulary"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    vocabulary_id = Column(Integer, index=True, nullable=False)
    wrong_count = Column(Integer, nullable=False, default=1)
    first_wrong_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_wrong_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")
