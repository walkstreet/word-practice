from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import PracticeRecord, User
from app.schemas import StatsResponse


router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=StatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    total_answered = db.query(PracticeRecord).filter(PracticeRecord.user_id == user.id).count()
    correct_count = (
        db.query(func.count(PracticeRecord.id))
        .filter(PracticeRecord.user_id == user.id, PracticeRecord.is_correct.is_(True))
        .scalar()
    )
    wrong_count = total_answered - correct_count
    accuracy = (correct_count / total_answered) if total_answered > 0 else 0.0

    return StatsResponse(
        total_answered=total_answered,
        correct_count=correct_count,
        wrong_count=wrong_count,
        accuracy=round(accuracy, 4),
    )
