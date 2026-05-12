import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db import get_db, get_vocab_db
from app.deps import get_current_user, verify_dify_import_api_key
from app.models import PracticeRecord, User, Vocabulary, WrongBook
from app.schemas import (
    DifyVocabImportBatch,
    DifyVocabImportItem,
    ImportResponse,
    VocabularyBatchDeleteBody,
    VocabularyBatchDeleteResponse,
    VocabularyItem,
    VocabularyListResponse,
    VocabularyUpdateBody,
)
from app.services.masking import normalize_word
from app.services.phonetic import normalize_phonetic
from app.services.senses import flatten_senses_to_legacy, normalize_sense_dicts, to_sense_out_list


router = APIRouter(tags=["vocab"])

_BATCH_DELETE_MAX = 500


def delete_vocabulary_ids(db: Session, vocab_db: Session, ids: list[int]) -> tuple[int, int]:
    """按 id 批量删除词条及其 practice_record / wrong_book。返回 (删除条数, 请求中不存在的 id 数)。"""
    order = list(dict.fromkeys(int(i) for i in ids if i is not None))
    if not order:
        return 0, 0
    found_rows = vocab_db.query(Vocabulary.id).filter(Vocabulary.id.in_(order)).all()
    found_ids = [r[0] for r in found_rows]
    found_set = set(found_ids)
    not_found = sum(1 for i in order if i not in found_set)
    if not found_ids:
        return 0, not_found
    db.query(PracticeRecord).filter(PracticeRecord.vocabulary_id.in_(found_ids)).delete(synchronize_session=False)
    db.query(WrongBook).filter(WrongBook.vocabulary_id.in_(found_ids)).delete(synchronize_session=False)
    deleted = vocab_db.query(Vocabulary).filter(Vocabulary.id.in_(found_ids)).delete(synchronize_session=False)
    return deleted, not_found


@router.get("/dify/ping")
def dify_ping(_: None = Depends(verify_dify_import_api_key)):
    """供 Dify/容器做 GET 连通与鉴权排查（与导入接口共用 x-api-key）。"""
    return {"status": "ok", "service": "word-practice"}


def import_vocabulary_from_rows(vocab_db: Session, rows: list[dict], *, source: str) -> ImportResponse:
    request_words = [normalize_word(str(r.get("word") or "")) for r in rows]
    total = 0
    success = 0
    duplicated_skipped = 0
    errors: list[dict] = []
    duplicate_skips: list[dict] = []
    pending_words: set[str] = set()
    staged: list[tuple[int, Vocabulary]] = []

    for line_number, row in enumerate(rows, start=2):
        total += 1
        word = normalize_word(str(row.get("word") or ""))
        phonetic = normalize_phonetic(str(row.get("phonetic") or ""))
        row_pos = str(row.get("part_of_speech") or row.get("pos") or "").strip()

        senses_stored = normalize_sense_dicts(row.get("senses") or [])
        if senses_stored:
            translation, part_of_speech = flatten_senses_to_legacy(senses_stored)
        else:
            translation = str(row.get("translation") or "").strip()
            part_of_speech = row_pos

        if not word:
            errors.append({"line": line_number, "word": "", "reason": "word empty"})
            continue
        if not senses_stored and not translation:
            raw_senses = row.get("senses")
            if isinstance(raw_senses, list) and len(raw_senses) > 0:
                reason = "senses present but no valid meaning (check each sense has non-empty meaning)"
            else:
                reason = "translation empty (need translation column or valid senses[])"
            errors.append({"line": line_number, "word": word, "reason": reason})
            continue

        normalized = normalize_word(word)
        if word in pending_words:
            duplicated_skipped += 1
            duplicate_skips.append(
                {"line": line_number, "word": word, "dedup_key": normalized, "reason": "duplicate in this batch"}
            )
            continue
        existing = vocab_db.query(Vocabulary).filter(Vocabulary.word == word).first()
        if existing:
            duplicated_skipped += 1
            duplicate_skips.append(
                {
                    "line": line_number,
                    "word": word,
                    "dedup_key": normalized,
                    "reason": "already in vocabulary",
                    "existing_id": existing.id,
                    "existing_word": existing.word,
                }
            )
            continue

        pending_words.add(word)
        row_obj = Vocabulary(
            word=word,
            translation=translation,
            phonetic=phonetic,
            part_of_speech=part_of_speech,
            normalized_word=normalized,
            source=source,
            senses=senses_stored,
        )
        vocab_db.add(row_obj)
        staged.append((line_number, row_obj))
        success += 1

    vocab_db.commit()
    inserted_rows: list[dict] = []
    for line_number, v in staged:
        vocab_db.refresh(v)
        inserted_rows.append({"line": line_number, "id": v.id, "word": v.word})
    failed = len(errors)

    return ImportResponse(
        total=total,
        success=success,
        failed=failed,
        duplicated_skipped=duplicated_skipped,
        errors=errors,
        duplicate_skips=duplicate_skips,
        request_words=request_words,
        inserted=inserted_rows,
    )


@router.post("/vocab/batch-delete", response_model=VocabularyBatchDeleteResponse)
def batch_delete_vocab(
    body: VocabularyBatchDeleteBody,
    db: Session = Depends(get_db),
    vocab_db: Session = Depends(get_vocab_db),
    _: User = Depends(get_current_user),
):
    if not body.ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids must not be empty")
    order = list(dict.fromkeys(body.ids))
    if len(order) > _BATCH_DELETE_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"at most {_BATCH_DELETE_MAX} ids per request",
        )
    deleted, not_found = delete_vocabulary_ids(db, vocab_db, order)
    db.commit()
    vocab_db.commit()
    return VocabularyBatchDeleteResponse(deleted=deleted, not_found=not_found)


@router.patch("/vocab/{vocabulary_id}", response_model=VocabularyItem)
def update_vocab(
    vocabulary_id: int,
    body: VocabularyUpdateBody,
    vocab_db: Session = Depends(get_vocab_db),
    _: User = Depends(get_current_user),
):
    row = vocab_db.query(Vocabulary).filter(Vocabulary.id == vocabulary_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary not found")

    w = normalize_word(body.word)
    if w != row.word:
        clash = vocab_db.query(Vocabulary).filter(Vocabulary.word == w, Vocabulary.id != vocabulary_id).first()
        if clash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="word already exists")

    phonetic = normalize_phonetic(body.phonetic)
    if body.senses:
        senses_stored = normalize_sense_dicts([s.model_dump() for s in body.senses])
        translation, part_of_speech = flatten_senses_to_legacy(senses_stored)
    else:
        translation = (body.translation or "").strip()
        part_of_speech = (body.part_of_speech or "").strip()
        senses_stored = None

    new_norm = normalize_word(w)
    row.word = w
    row.normalized_word = new_norm
    row.phonetic = phonetic
    row.translation = translation
    row.part_of_speech = part_of_speech
    row.senses = senses_stored
    vocab_db.commit()
    vocab_db.refresh(row)

    return VocabularyItem(
        id=row.id,
        word=row.word,
        translation=row.translation,
        phonetic=row.phonetic or "",
        part_of_speech=row.part_of_speech or "",
        senses=to_sense_out_list(row.senses),
    )


@router.delete("/vocab/{vocabulary_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vocab(
    vocabulary_id: int,
    db: Session = Depends(get_db),
    vocab_db: Session = Depends(get_vocab_db),
    _: User = Depends(get_current_user),
):
    deleted, _ = delete_vocabulary_ids(db, vocab_db, [vocabulary_id])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary not found")
    db.commit()
    vocab_db.commit()


@router.get("/vocab", response_model=VocabularyListResponse)
def list_vocab(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    q: str | None = Query(default=None),
    vocab_db: Session = Depends(get_vocab_db),
    _: User = Depends(get_current_user),
):
    query = vocab_db.query(Vocabulary)
    if q:
        needle = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Vocabulary.word).like(needle),
                func.lower(Vocabulary.translation).like(needle),
                func.lower(Vocabulary.normalized_word).like(needle),
            )
        )
    total = query.count()
    rows = (
        query.order_by(Vocabulary.word.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return VocabularyListResponse(
        total=total,
        list=[
            VocabularyItem(
                id=row.id,
                word=row.word,
                translation=row.translation,
                phonetic=row.phonetic or "",
                part_of_speech=row.part_of_speech or "",
                senses=to_sense_out_list(row.senses),
            )
            for row in rows
        ],
    )


@router.post("/vocab/import", response_model=ImportResponse)
def import_vocab(
    file: UploadFile = File(...),
    vocab_db: Session = Depends(get_vocab_db),
    _: User = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV is supported")

    raw = file.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(raw))
    required = {"word", "translation"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must contain word,translation columns",
        )

    rows = list(reader)
    return import_vocabulary_from_rows(vocab_db, rows, source="import")


@router.post("/vocab/import/dify", response_model=ImportResponse)
def import_vocab_dify(
    batch: DifyVocabImportBatch,
    vocab_db: Session = Depends(get_vocab_db),
    _: None = Depends(verify_dify_import_api_key),
):
    rows = []
    for item in batch.items:
        d = item.model_dump()
        if item.senses is not None:
            d["senses"] = [s.model_dump() for s in item.senses]
        rows.append(d)
    return import_vocabulary_from_rows(vocab_db, rows, source="dify")
