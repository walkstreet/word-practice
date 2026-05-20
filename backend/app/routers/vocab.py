import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db import get_db, get_vocab_db
from app.deps import get_current_user, verify_dify_import_api_key
from app.models import PracticeRecord, User, VocabGroup, Vocabulary, WrongBook
from app.schemas import (
    DifyVocabImportBatch,
    DifyVocabImportItem,
    ImportResponse,
    VocabGroupCreateBody,
    VocabGroupDeleteBody,
    VocabGroupItem,
    VocabGroupListResponse,
    VocabGroupRenameBody,
    VocabularyBatchDeleteBody,
    VocabularyBatchDeleteResponse,
    VocabularyBatchMoveGroupBody,
    VocabularyBatchMoveGroupResponse,
    VocabularyItem,
    VocabularyListResponse,
    VocabularyUpdateBody,
)
from app.services.masking import normalize_word
from app.services.phonetic import normalize_phonetic
from app.services.senses import flatten_senses_to_legacy, normalize_sense_dicts, to_sense_out_list


router = APIRouter(tags=["vocab"])

_BATCH_DELETE_MAX = 500
GROUP_FILTER_ALL = "__ALL__"
GROUP_FILTER_UNGROUPED = "__UNGROUPED__"


def normalize_group_name(value: str | None) -> str:
    return (value or "").strip()


def validate_named_group(name: str) -> str:
    normalized = normalize_group_name(name)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="group name must not be empty")
    if normalized in {GROUP_FILTER_ALL, GROUP_FILTER_UNGROUPED}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reserved group name")
    return normalized


def ensure_named_group_exists(vocab_db: Session, name: str) -> None:
    if not name:
        return
    exists = vocab_db.query(VocabGroup.id).filter(VocabGroup.name == name).first()
    if exists:
        return
    vocab_db.add(VocabGroup(name=name))


def apply_group_filter(query, group_value: str | None):
    if group_value is None:
        return query
    normalized = group_value.strip()
    if not normalized or normalized == GROUP_FILTER_ALL:
        return query
    if normalized == GROUP_FILTER_UNGROUPED:
        return query.filter(Vocabulary.group_name == "")
    return query.filter(Vocabulary.group_name == normalized)


def build_group_items(vocab_db: Session) -> list[VocabGroupItem]:
    count_rows = vocab_db.query(Vocabulary.group_name, func.count(Vocabulary.id)).group_by(Vocabulary.group_name).all()
    count_map = {str(group_name or ""): int(count) for group_name, count in count_rows}
    names = {n for (n,) in vocab_db.query(VocabGroup.name).all()}
    names.update(name for name in count_map.keys() if name)
    ordered_named = sorted(names)
    items = [VocabGroupItem(name="", count=count_map.get("", 0))]
    items.extend(VocabGroupItem(name=name, count=count_map.get(name, 0)) for name in ordered_named)
    return items


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
            group_name="",
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


@router.post("/vocab/batch-move-group", response_model=VocabularyBatchMoveGroupResponse)
def batch_move_vocab_group(
    body: VocabularyBatchMoveGroupBody,
    vocab_db: Session = Depends(get_vocab_db),
    _: User = Depends(get_current_user),
):
    target_raw = (body.target_group or "").strip()
    if target_raw == GROUP_FILTER_ALL:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target_group cannot be __ALL__")
    if target_raw == GROUP_FILTER_UNGROUPED:
        target = ""
    else:
        target = normalize_group_name(target_raw)
        if target:
            target = validate_named_group(target)
            ensure_named_group_exists(vocab_db, target)

    has_ids = bool(body.ids)
    has_source_group = body.source_group is not None
    if has_ids == has_source_group:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="provide either ids or source_group",
        )

    if has_ids:
        order = list(dict.fromkeys(int(i) for i in (body.ids or []) if i is not None))
        if not order:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ids must not be empty")
        if len(order) > _BATCH_DELETE_MAX:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"at most {_BATCH_DELETE_MAX} ids per request",
            )
        found_rows = vocab_db.query(Vocabulary.id).filter(Vocabulary.id.in_(order)).all()
        found_ids = [r[0] for r in found_rows]
        found_set = set(found_ids)
        not_found = sum(1 for i in order if i not in found_set)
        if not found_ids:
            return VocabularyBatchMoveGroupResponse(moved=0, not_found=not_found)
        moved = (
            vocab_db.query(Vocabulary)
            .filter(Vocabulary.id.in_(found_ids))
            .update({Vocabulary.group_name: target}, synchronize_session=False)
        )
        vocab_db.commit()
        return VocabularyBatchMoveGroupResponse(moved=moved, not_found=not_found)

    source_raw = (body.source_group or "").strip()
    if source_raw == GROUP_FILTER_ALL:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_group cannot be __ALL__")
    if source_raw == GROUP_FILTER_UNGROUPED or source_raw == "":
        source = ""
    else:
        source = validate_named_group(source_raw)
    if source == target:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source and target must be different")
    moved = (
        vocab_db.query(Vocabulary)
        .filter(Vocabulary.group_name == source)
        .update({Vocabulary.group_name: target}, synchronize_session=False)
    )
    vocab_db.commit()
    return VocabularyBatchMoveGroupResponse(moved=moved, not_found=0)


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
    if body.group_name is not None:
        row.group_name = normalize_group_name(body.group_name)
        ensure_named_group_exists(vocab_db, row.group_name)
    row.senses = senses_stored
    vocab_db.commit()
    vocab_db.refresh(row)

    return VocabularyItem(
        id=row.id,
        word=row.word,
        translation=row.translation,
        phonetic=row.phonetic or "",
        part_of_speech=row.part_of_speech or "",
        group_name=row.group_name or "",
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
    group: str | None = Query(default=None),
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
    query = apply_group_filter(query, group)
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
                group_name=row.group_name or "",
                senses=to_sense_out_list(row.senses),
            )
            for row in rows
        ],
    )


@router.get("/vocab/groups", response_model=VocabGroupListResponse)
def list_vocab_groups(
    vocab_db: Session = Depends(get_vocab_db),
    _: User = Depends(get_current_user),
):
    return VocabGroupListResponse(list=build_group_items(vocab_db))


@router.post("/vocab/groups", response_model=VocabGroupListResponse)
def create_vocab_group(
    body: VocabGroupCreateBody,
    vocab_db: Session = Depends(get_vocab_db),
    _: User = Depends(get_current_user),
):
    name = validate_named_group(body.name)
    exists = vocab_db.query(VocabGroup.id).filter(VocabGroup.name == name).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="group already exists")
    vocab_db.add(VocabGroup(name=name))
    vocab_db.commit()
    return VocabGroupListResponse(list=build_group_items(vocab_db))


@router.post("/vocab/groups/rename", response_model=VocabGroupListResponse)
def rename_vocab_group(
    body: VocabGroupRenameBody,
    vocab_db: Session = Depends(get_vocab_db),
    _: User = Depends(get_current_user),
):
    from_name = validate_named_group(body.from_name)
    to_name = normalize_group_name(body.to_name)
    if to_name:
        to_name = validate_named_group(to_name)
    if from_name == to_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="from_name and to_name must be different")
    source_group = vocab_db.query(VocabGroup).filter(VocabGroup.name == from_name).first()
    source_count = vocab_db.query(Vocabulary.id).filter(Vocabulary.group_name == from_name).count()
    if source_group is None and source_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="group not found")
    if to_name:
        ensure_named_group_exists(vocab_db, to_name)
    vocab_db.query(Vocabulary).filter(Vocabulary.group_name == from_name).update(
        {Vocabulary.group_name: to_name}, synchronize_session=False
    )
    if source_group is not None:
        vocab_db.delete(source_group)
    vocab_db.commit()
    return VocabGroupListResponse(list=build_group_items(vocab_db))


@router.post("/vocab/groups/delete", response_model=VocabGroupListResponse)
def delete_vocab_group(
    body: VocabGroupDeleteBody,
    vocab_db: Session = Depends(get_vocab_db),
    _: User = Depends(get_current_user),
):
    from_name = validate_named_group(body.name)
    target_raw = body.target.strip()
    if target_raw == GROUP_FILTER_UNGROUPED:
        target = ""
    elif target_raw == GROUP_FILTER_ALL:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target cannot be __ALL__")
    else:
        target = validate_named_group(target_raw)
    if from_name == target:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target must be different")
    source_group = vocab_db.query(VocabGroup).filter(VocabGroup.name == from_name).first()
    source_count = vocab_db.query(Vocabulary.id).filter(Vocabulary.group_name == from_name).count()
    if source_group is None and source_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="group not found")
    if target:
        ensure_named_group_exists(vocab_db, target)
    vocab_db.query(Vocabulary).filter(Vocabulary.group_name == from_name).update(
        {Vocabulary.group_name: target}, synchronize_session=False
    )
    if source_group is not None:
        vocab_db.delete(source_group)
    vocab_db.commit()
    return VocabGroupListResponse(list=build_group_items(vocab_db))


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
