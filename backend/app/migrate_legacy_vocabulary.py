"""从旧版单库（word_practice.db 内含 vocabulary 表）迁出词条到独立 vocabulary.db。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _table_exists(engine: Engine, name: str) -> bool:
    return name in inspect(engine).get_table_names()


def _row_count(conn, table: str) -> int:
    return int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)


def _rebuild_practice_record(conn) -> None:
    conn.execute(text("ALTER TABLE practice_record RENAME TO practice_record__old"))
    conn.execute(
        text(
            """
            CREATE TABLE practice_record (
                id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                vocabulary_id INTEGER NOT NULL,
                question_mask VARCHAR(255) NOT NULL,
                missing_positions JSON NOT NULL,
                user_answer VARCHAR(128) NOT NULL,
                correct_answer VARCHAR(128) NOT NULL,
                is_correct BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY(user_id) REFERENCES users (id)
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO practice_record (
                id, user_id, vocabulary_id, question_mask, missing_positions,
                user_answer, correct_answer, is_correct, created_at
            )
            SELECT
                id, user_id, vocabulary_id, question_mask, missing_positions,
                user_answer, correct_answer, is_correct, created_at
            FROM practice_record__old
            """
        )
    )
    conn.execute(text("DROP TABLE practice_record__old"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_practice_record_id ON practice_record (id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_practice_record_user_id ON practice_record (user_id)"))
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_practice_record_vocabulary_id "
            "ON practice_record (vocabulary_id)"
        )
    )


def _rebuild_wrong_book(conn) -> None:
    conn.execute(text("ALTER TABLE wrong_book RENAME TO wrong_book__old"))
    conn.execute(
        text(
            """
            CREATE TABLE wrong_book (
                id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                vocabulary_id INTEGER NOT NULL,
                wrong_count INTEGER NOT NULL,
                first_wrong_at DATETIME NOT NULL,
                last_wrong_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT uq_user_vocabulary UNIQUE (user_id, vocabulary_id),
                FOREIGN KEY(user_id) REFERENCES users (id)
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO wrong_book (
                id, user_id, vocabulary_id, wrong_count,
                first_wrong_at, last_wrong_at
            )
            SELECT
                id, user_id, vocabulary_id, wrong_count,
                first_wrong_at, last_wrong_at
            FROM wrong_book__old
            """
        )
    )
    conn.execute(text("DROP TABLE wrong_book__old"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_wrong_book_id ON wrong_book (id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_wrong_book_user_id ON wrong_book (user_id)"))
    conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_wrong_book_vocabulary_id ON wrong_book (vocabulary_id)")
    )


def _serialize_senses(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, str):
        return val
    return json.dumps(val, ensure_ascii=False)


def _referenced_fk_tables(conn, table: str) -> set[str]:
    """PRAGMA foreign_key_list：被引用表名为第 3 列（0-based 索引为 2）。"""
    rows = conn.execute(text(f"PRAGMA foreign_key_list({table})")).fetchall()
    return {r[2] for r in rows}


def repair_app_db_if_vocab_table_missing(engine: Engine) -> None:
    """修复误删 vocabulary 表但子表仍引用该 FK 的中间状态。"""
    if _table_exists(engine, "vocabulary"):
        return
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        try:
            if _table_exists(engine, "practice_record") and "vocabulary" in _referenced_fk_tables(
                conn, "practice_record"
            ):
                _rebuild_practice_record(conn)
            if _table_exists(engine, "wrong_book") and "vocabulary" in _referenced_fk_tables(conn, "wrong_book"):
                _rebuild_wrong_book(conn)
        finally:
            conn.execute(text("PRAGMA foreign_keys=ON"))


def migrate_split_vocabulary_if_needed(engine: Engine, vocab_engine: Engine) -> None:
    if not _table_exists(engine, "vocabulary"):
        return

    with engine.connect() as main_conn:
        main_vocab_n = _row_count(main_conn, "vocabulary")

    if main_vocab_n == 0:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            try:
                if _table_exists(engine, "practice_record") and _table_exists(engine, "vocabulary"):
                    if "vocabulary" in _referenced_fk_tables(conn, "practice_record"):
                        _rebuild_practice_record(conn)
                if _table_exists(engine, "wrong_book") and _table_exists(engine, "vocabulary"):
                    if "vocabulary" in _referenced_fk_tables(conn, "wrong_book"):
                        _rebuild_wrong_book(conn)
                if _table_exists(engine, "vocabulary"):
                    conn.execute(text("DROP TABLE vocabulary"))
            finally:
                conn.execute(text("PRAGMA foreign_keys=ON"))
        return

    with engine.connect() as main_conn:
        rows = main_conn.execute(text("SELECT * FROM vocabulary")).mappings().all()

    if not rows:
        return

    with vocab_engine.begin() as vconn:
        if not _table_exists(vocab_engine, "vocabulary"):
            return
        existing_ids = {r[0] for r in vconn.execute(text("SELECT id FROM vocabulary")).fetchall()}
        insert_sql = text(
            """
            INSERT INTO vocabulary (
                id, word, translation, phonetic, part_of_speech, senses,
                normalized_word, source, created_at
            ) VALUES (
                :id, :word, :translation, :phonetic, :part_of_speech, :senses,
                :normalized_word, :source, :created_at
            )
            """
        )
        for r in rows:
            rid = int(r["id"])
            if rid in existing_ids:
                continue
            d = dict(r)
            d["senses"] = _serialize_senses(d.get("senses"))
            vconn.execute(insert_sql, d)
            existing_ids.add(rid)

    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        try:
            if "vocabulary" in _referenced_fk_tables(conn, "practice_record"):
                _rebuild_practice_record(conn)
            if "vocabulary" in _referenced_fk_tables(conn, "wrong_book"):
                _rebuild_wrong_book(conn)
            conn.execute(text("DROP TABLE IF EXISTS vocabulary"))
        finally:
            conn.execute(text("PRAGMA foreign_keys=ON"))
