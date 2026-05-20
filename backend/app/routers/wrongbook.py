from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db, get_vocab_db
from app.deps import get_current_user
from app.models import User, Vocabulary, WrongBook
from app.schemas import WrongBookItem, WrongBookResponse
from app.services.senses import to_sense_out_list


router = APIRouter(prefix="/wrongbook", tags=["wrongbook"])


def to_current_timezone(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


@router.get("", response_model=WrongBookResponse)
def list_wrongbook(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    vocab_db: Session = Depends(get_vocab_db),
    user: User = Depends(get_current_user),
):
    query = db.query(WrongBook).filter(WrongBook.user_id == user.id)
    total = query.count()
    rows = (
        query.order_by(WrongBook.last_wrong_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for row in rows:
        vocab = vocab_db.query(Vocabulary).filter(Vocabulary.id == row.vocabulary_id).first()
        items.append(
            WrongBookItem(
                vocabulary_id=row.vocabulary_id,
                word=vocab.word if vocab else "",
                translation=vocab.translation if vocab else "",
                phonetic=vocab.phonetic if vocab else "",
                part_of_speech=vocab.part_of_speech if vocab else "",
                senses=to_sense_out_list(vocab.senses) if vocab else None,
                wrong_count=row.wrong_count,
                last_wrong_at=to_current_timezone(row.last_wrong_at),
            )
        )

    return WrongBookResponse(total=total, list=items)
