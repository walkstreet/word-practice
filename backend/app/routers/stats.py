from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import PracticeRecord, User, StatsSnapshot
from app.schemas import StatsResponse, StatsSnapshotResponse


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


@router.delete("")
def reset_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """清零统计数据（删除所有练习记录）"""
    db.query(PracticeRecord).filter(PracticeRecord.user_id == user.id).delete()
    db.commit()
    return {"message": "统计数据已清零"}


@router.post("/snapshots")
def save_stats_snapshot(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """保存当前统计数据快照"""
    total_answered = db.query(PracticeRecord).filter(PracticeRecord.user_id == user.id).count()
    correct_count = (
        db.query(func.count(PracticeRecord.id))
        .filter(PracticeRecord.user_id == user.id, PracticeRecord.is_correct.is_(True))
        .scalar()
    )
    wrong_count = total_answered - correct_count
    accuracy = (correct_count / total_answered) if total_answered > 0 else 0.0

    snapshot = StatsSnapshot(
        user_id=user.id,
        total_answered=total_answered,
        correct_count=correct_count,
        wrong_count=wrong_count,
        accuracy=f"{(accuracy * 100):.2f}%",
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return {"id": snapshot.id, "message": "快照保存成功"}


@router.get("/snapshots", response_model=StatsSnapshotResponse)
def get_stats_snapshots(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取所有保存的统计快照"""
    snapshots = (
        db.query(StatsSnapshot)
        .filter(StatsSnapshot.user_id == user.id)
        .order_by(StatsSnapshot.created_at.desc())
        .all()
    )
    return StatsSnapshotResponse(total=len(snapshots), list=snapshots)


@router.delete("/snapshots/{snapshot_id}")
def delete_stats_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除指定的统计快照"""
    snapshot = (
        db.query(StatsSnapshot)
        .filter(StatsSnapshot.id == snapshot_id, StatsSnapshot.user_id == user.id)
        .first()
    )
    if not snapshot:
        return {"message": "快照不存在"}
    
    db.delete(snapshot)
    db.commit()
    return {"message": "快照已删除"}
