import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import PracticeRecord, User, Vocabulary, WrongBook
from app.schemas import (
    NextQuestionResponse,
    PracticeHistoryItem,
    PracticeHistoryResponse,
    SubmitRequest,
    SubmitResponse,
)
from app.security import create_question_token, decode_question_token
from app.services.masking import (
    assemble_surface,
    build_masked_segment_payload,
    build_masked_word,
    choose_missing_positions,
    compact_phrase,
    phrase_ordered_parts,
    pick_primary_answer,
    segments_payload_to_mask_string,
)
from app.services.senses import to_sense_out_list


router = APIRouter(prefix="/practice", tags=["practice"])


def to_current_timezone(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


@router.get("/next", response_model=NextQuestionResponse)
def next_question(
    scope: str = Query(default="all"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if scope not in {"all", "wrongbook"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scope must be all or wrongbook")

    if scope == "wrongbook":
        ids = db.query(WrongBook.vocabulary_id).filter(WrongBook.user_id == user.id).all()
    else:
        ids = db.query(Vocabulary.id).all()
    if not ids:
        if scope == "wrongbook":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wrong book is empty")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary is empty")

    vocabulary_id = random.choice(ids)[0]
    vocab = db.query(Vocabulary).filter(Vocabulary.id == vocabulary_id).first()
    primary = pick_primary_answer(vocab.word)
    ordered = phrase_ordered_parts(primary)
    words = [text for kind, text in ordered if kind == "word"]
    compact = compact_phrase(words)
    missing_positions = choose_missing_positions(compact)
    masked_segments = build_masked_segment_payload(ordered, missing_positions)
    mask_for_record = segments_payload_to_mask_string(masked_segments)
    masked_word_flat = build_masked_word(compact, missing_positions)

    question_token = create_question_token(
        {
            "user_id": user.id,
            "vocabulary_id": vocab.id,
            "missing_positions": missing_positions,
            "masked_word": mask_for_record,
        }
    )

    return NextQuestionResponse(
        question_id=question_token,
        vocabulary_id=vocab.id,
        word=vocab.word,
        translation=vocab.translation,
        phonetic=vocab.phonetic,
        part_of_speech=vocab.part_of_speech,
        senses=to_sense_out_list(vocab.senses),
        masked_word=masked_word_flat,
        masked_segments=masked_segments,
        hint={"wordLength": len(compact), "missingCount": len(missing_positions)},
    )


@router.post("/submit", response_model=SubmitResponse)
def submit_answer(
    payload: SubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        question_payload = decode_question_token(payload.question_id)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid question_id") from exc

    if int(question_payload.get("vocabulary_id", -1)) != payload.vocabulary_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="question_id does not match vocabulary_id")
    if int(question_payload.get("user_id", -1)) != user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="question_id does not match user")

    vocab = db.query(Vocabulary).filter(Vocabulary.id == payload.vocabulary_id).first()
    if not vocab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary not found")

    missing_positions = question_payload.get("missing_positions", [])
    primary = pick_primary_answer(vocab.word)
    ordered = phrase_ordered_parts(primary)
    words = [text for kind, text in ordered if kind == "word"]
    compact = compact_phrase(words)
    expected_missing = "".join(compact[idx] for idx in missing_positions)
    provided_missing = payload.missing_letters
    # V1 rule: only ignore case.
    is_correct = provided_missing.lower() == expected_missing.lower()
    wrong_blank_indexes = []
    for idx, expected_char in enumerate(expected_missing):
        provided_char = provided_missing[idx] if idx < len(provided_missing) else ""
        if provided_char.lower() != expected_char.lower():
            wrong_blank_indexes.append(idx)

    # Reconstruct user attempted phrase for record keeping（保留省略号、空格等字面量）.
    attempted_chars = list(compact)
    for offset, pos in enumerate(missing_positions):
        if offset < len(provided_missing):
            attempted_chars[pos] = provided_missing[offset]
    filled_compact = "".join(attempted_chars)
    idx = 0
    rebuilt: list[str] = []
    for w in words:
        L = len(w)
        rebuilt.append(filled_compact[idx : idx + L])
        idx += L
    attempted_word = assemble_surface(ordered, rebuilt)

    canonical_display = assemble_surface(ordered, words) if words else vocab.word

    record = PracticeRecord(
        user_id=user.id,
        vocabulary_id=vocab.id,
        question_mask=question_payload.get("masked_word", ""),
        missing_positions=missing_positions,
        user_answer=attempted_word,
        correct_answer=vocab.word,
        is_correct=is_correct,
    )
    db.add(record)

    if not is_correct:
        wrong = (
            db.query(WrongBook)
            .filter(WrongBook.user_id == user.id, WrongBook.vocabulary_id == vocab.id)
            .first()
        )
        if wrong:
            wrong.wrong_count += 1
        else:
            wrong = WrongBook(user_id=user.id, vocabulary_id=vocab.id, wrong_count=1)
            db.add(wrong)

    db.commit()

    if is_correct:
        return SubmitResponse(
            is_correct=True,
            correct_answer=canonical_display,
            message="回答正确",
            wrong_blank_indexes=[],
        )
    return SubmitResponse(
        is_correct=False,
        correct_answer=canonical_display,
        message=f"回答错误，正确答案是 {canonical_display}",
        wrong_blank_indexes=wrong_blank_indexes,
    )


@router.get("/history", response_model=PracticeHistoryResponse)
def practice_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(PracticeRecord).filter(PracticeRecord.user_id == user.id)
    total = query.count()
    rows = (
        query.order_by(PracticeRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for row in rows:
        vocab = db.query(Vocabulary).filter(Vocabulary.id == row.vocabulary_id).first()
        items.append(
            PracticeHistoryItem(
                vocabulary_id=row.vocabulary_id,
                word=vocab.word if vocab else "",
                translation=vocab.translation if vocab else "",
                phonetic=vocab.phonetic if vocab else "",
                part_of_speech=vocab.part_of_speech if vocab else "",
                senses=to_sense_out_list(vocab.senses) if vocab else None,
                question_mask=row.question_mask,
                user_answer=row.user_answer,
                correct_answer=row.correct_answer,
                is_correct=row.is_correct,
                created_at=to_current_timezone(row.created_at),
            )
        )

    return PracticeHistoryResponse(total=total, list=items)
