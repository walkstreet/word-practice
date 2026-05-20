from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.db import SessionLocal, VocabSessionLocal
from app.models import PracticeRecord, StatsSnapshot, User, Vocabulary, WrongBook
from app.services.masking import normalize_word
from app.services.phonetic import normalize_phonetic
from app.services.senses import normalize_sense_dicts


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _parse_dt(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass
    return datetime.utcnow()


def _parse_json(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return default
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return default
    return default


def _build_record_signature(
    vocabulary_id: int,
    question_mask: str,
    missing_positions: Any,
    user_answer: str,
    correct_answer: str,
    is_correct: bool,
    created_at: datetime,
) -> tuple[Any, ...]:
    return (
        vocabulary_id,
        question_mask,
        json.dumps(missing_positions, ensure_ascii=False, sort_keys=True),
        user_answer,
        correct_answer,
        bool(is_correct),
        created_at.isoformat(),
    )


def migrate_user_data(source_db_path: Path, source_username: str, target_username: str) -> dict[str, int]:
    src_conn = sqlite3.connect(str(source_db_path))
    src_conn.row_factory = sqlite3.Row

    app_db = SessionLocal()
    vocab_db = VocabSessionLocal()
    summary = {
        "source_practice_rows": 0,
        "source_wrong_rows": 0,
        "source_snapshot_rows": 0,
        "vocab_created": 0,
        "wrongbook_upserted": 0,
        "practice_inserted": 0,
        "snapshot_inserted": 0,
        "skipped_missing_vocab": 0,
    }

    try:
        target_user = app_db.query(User).filter(User.username == target_username).first()
        if target_user is None:
            raise RuntimeError(f"target user not found: {target_username}")

        if not _table_exists(src_conn, "users"):
            raise RuntimeError("source database has no users table")
        source_user = src_conn.execute(
            "SELECT id FROM users WHERE username = ? LIMIT 1",
            (source_username,),
        ).fetchone()
        if source_user is None:
            raise RuntimeError(f"source user not found: {source_username}")
        source_user_id = int(source_user["id"])

        source_practice_rows: list[sqlite3.Row] = []
        source_wrong_rows: list[sqlite3.Row] = []
        source_snapshot_rows: list[sqlite3.Row] = []

        if _table_exists(src_conn, "practice_record"):
            source_practice_rows = src_conn.execute(
                "SELECT * FROM practice_record WHERE user_id = ? ORDER BY id ASC",
                (source_user_id,),
            ).fetchall()
        if _table_exists(src_conn, "wrong_book"):
            source_wrong_rows = src_conn.execute(
                "SELECT * FROM wrong_book WHERE user_id = ? ORDER BY id ASC",
                (source_user_id,),
            ).fetchall()
        if _table_exists(src_conn, "stats_snapshot"):
            source_snapshot_rows = src_conn.execute(
                "SELECT * FROM stats_snapshot WHERE user_id = ? ORDER BY id ASC",
                (source_user_id,),
            ).fetchall()

        summary["source_practice_rows"] = len(source_practice_rows)
        summary["source_wrong_rows"] = len(source_wrong_rows)
        summary["source_snapshot_rows"] = len(source_snapshot_rows)

        source_vocab_ids = {
            int(r["vocabulary_id"]) for r in source_practice_rows + source_wrong_rows if r["vocabulary_id"] is not None
        }

        source_vocab_by_id: dict[int, sqlite3.Row] = {}
        if source_vocab_ids and _table_exists(src_conn, "vocabulary"):
            placeholders = ",".join("?" for _ in source_vocab_ids)
            rows = src_conn.execute(
                f"SELECT * FROM vocabulary WHERE id IN ({placeholders})",
                tuple(sorted(source_vocab_ids)),
            ).fetchall()
            source_vocab_by_id = {int(r["id"]): r for r in rows}

        vocab_id_map: dict[int, int] = {}
        for source_vocab_id in sorted(source_vocab_ids):
            src_vocab = source_vocab_by_id.get(source_vocab_id)
            if src_vocab is None:
                summary["skipped_missing_vocab"] += 1
                continue
            word = normalize_word(str(src_vocab["word"] or ""))
            if not word:
                summary["skipped_missing_vocab"] += 1
                continue
            existing = vocab_db.query(Vocabulary).filter(Vocabulary.normalized_word == word).first()
            if existing is not None:
                vocab_id_map[source_vocab_id] = int(existing.id)
                continue
            senses = normalize_sense_dicts(_parse_json(src_vocab["senses"], []))
            row = Vocabulary(
                word=word,
                normalized_word=word,
                translation=str(src_vocab["translation"] or "").strip(),
                phonetic=normalize_phonetic(str(src_vocab["phonetic"] or "")),
                part_of_speech=str(src_vocab["part_of_speech"] or "").strip(),
                senses=senses or None,
                source="legacy_migration",
                group_name="",
                created_at=_parse_dt(src_vocab["created_at"]),
            )
            vocab_db.add(row)
            vocab_db.flush()
            vocab_id_map[source_vocab_id] = int(row.id)
            summary["vocab_created"] += 1

        existing_wrong_rows = app_db.query(WrongBook).filter(WrongBook.user_id == target_user.id).all()
        existing_wrong_by_vocab = {int(r.vocabulary_id): r for r in existing_wrong_rows}
        for row in source_wrong_rows:
            source_vocab_id = int(row["vocabulary_id"])
            target_vocab_id = vocab_id_map.get(source_vocab_id)
            if target_vocab_id is None:
                summary["skipped_missing_vocab"] += 1
                continue
            existing = existing_wrong_by_vocab.get(target_vocab_id)
            source_wrong_count = int(row["wrong_count"] or 0)
            source_first = _parse_dt(row["first_wrong_at"])
            source_last = _parse_dt(row["last_wrong_at"])
            if existing is None:
                entity = WrongBook(
                    user_id=target_user.id,
                    vocabulary_id=target_vocab_id,
                    wrong_count=max(1, source_wrong_count),
                    first_wrong_at=source_first,
                    last_wrong_at=source_last,
                )
                app_db.add(entity)
                existing_wrong_by_vocab[target_vocab_id] = entity
            else:
                existing.wrong_count = int(existing.wrong_count or 0) + max(0, source_wrong_count)
                existing.first_wrong_at = min(existing.first_wrong_at, source_first)
                existing.last_wrong_at = max(existing.last_wrong_at, source_last)
            summary["wrongbook_upserted"] += 1

        existing_records = app_db.query(PracticeRecord).filter(PracticeRecord.user_id == target_user.id).all()
        existing_record_signatures = {
            _build_record_signature(
                int(r.vocabulary_id),
                r.question_mask,
                r.missing_positions,
                r.user_answer,
                r.correct_answer,
                bool(r.is_correct),
                r.created_at,
            )
            for r in existing_records
        }
        for row in source_practice_rows:
            source_vocab_id = int(row["vocabulary_id"])
            target_vocab_id = vocab_id_map.get(source_vocab_id)
            if target_vocab_id is None:
                summary["skipped_missing_vocab"] += 1
                continue
            missing_positions = _parse_json(row["missing_positions"], [])
            created_at = _parse_dt(row["created_at"])
            sig = _build_record_signature(
                target_vocab_id,
                str(row["question_mask"] or ""),
                missing_positions,
                str(row["user_answer"] or ""),
                str(row["correct_answer"] or ""),
                bool(row["is_correct"]),
                created_at,
            )
            if sig in existing_record_signatures:
                continue
            app_db.add(
                PracticeRecord(
                    user_id=target_user.id,
                    vocabulary_id=target_vocab_id,
                    question_mask=str(row["question_mask"] or ""),
                    missing_positions=missing_positions,
                    user_answer=str(row["user_answer"] or ""),
                    correct_answer=str(row["correct_answer"] or ""),
                    is_correct=bool(row["is_correct"]),
                    created_at=created_at,
                )
            )
            existing_record_signatures.add(sig)
            summary["practice_inserted"] += 1

        existing_snapshots = app_db.query(StatsSnapshot).filter(StatsSnapshot.user_id == target_user.id).all()
        existing_snapshot_signatures = {
            (
                int(s.total_answered),
                int(s.correct_count),
                int(s.wrong_count),
                str(s.accuracy),
                s.created_at.isoformat(),
            )
            for s in existing_snapshots
        }
        for row in source_snapshot_rows:
            created_at = _parse_dt(row["created_at"])
            sig = (
                int(row["total_answered"] or 0),
                int(row["correct_count"] or 0),
                int(row["wrong_count"] or 0),
                str(row["accuracy"] or "0.00%"),
                created_at.isoformat(),
            )
            if sig in existing_snapshot_signatures:
                continue
            app_db.add(
                StatsSnapshot(
                    user_id=target_user.id,
                    total_answered=int(row["total_answered"] or 0),
                    correct_count=int(row["correct_count"] or 0),
                    wrong_count=int(row["wrong_count"] or 0),
                    accuracy=str(row["accuracy"] or "0.00%"),
                    created_at=created_at,
                )
            )
            existing_snapshot_signatures.add(sig)
            summary["snapshot_inserted"] += 1

        vocab_db.commit()
        app_db.commit()
        return summary
    except Exception:
        vocab_db.rollback()
        app_db.rollback()
        raise
    finally:
        src_conn.close()
        vocab_db.close()
        app_db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate stats and wrong-book words from an old word_practice.db file")
    parser.add_argument("--source-db", required=True, help="path to old word_practice.db")
    parser.add_argument("--source-username", default="admin", help="username in source db, default: admin")
    parser.add_argument("--target-username", default="admin", help="username in current db, default: admin")
    args = parser.parse_args()

    source_db = Path(args.source_db).expanduser().resolve()
    if not source_db.exists():
        raise SystemExit(f"source db not found: {source_db}")

    summary = migrate_user_data(
        source_db_path=source_db,
        source_username=args.source_username.strip(),
        target_username=args.target_username.strip(),
    )
    print("Migration finished:")
    for key, value in summary.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
