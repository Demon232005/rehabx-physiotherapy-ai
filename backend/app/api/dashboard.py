"""Dashboard aggregate endpoint."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbDep
from app.models import AiAnalysis, Exercise, ExerciseSession, Progress, RehabilitationRecommendation
from app.schemas import AnalysisDetailOut, DashboardOut

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(user: CurrentUser, db: DbDep) -> DashboardOut:
    analyses = db.scalars(
        select(AiAnalysis)
        .where(AiAnalysis.user_id == user.id)
        .options(
            selectinload(AiAnalysis.upload),
            selectinload(AiAnalysis.regions),
            selectinload(AiAnalysis.recommendation),
        )
        .order_by(AiAnalysis.created_at.desc())
        .limit(10)
    )
    analysis_list = list(analyses)
    completed = [a for a in analysis_list if a.status == "completed"]

    latest = completed[0] if completed else None
    latest_rec = None
    if latest and latest.recommendation:
        latest_rec = latest.recommendation

    sessions = db.scalars(
        select(ExerciseSession)
        .where(ExerciseSession.user_id == user.id)
        .options(selectinload(ExerciseSession.exercise))
        .order_by(ExerciseSession.created_at.desc())
        .limit(10)
    )
    session_list = list(sessions)
    upcoming = [s for s in session_list if s.status in ("planned", "in_progress")]

    progress_list = list(
        db.scalars(
            select(Progress).where(Progress.user_id == user.id).order_by(Progress.date.desc()).limit(20)
        )
    )

    total_analyses = db.scalar(
        select(func.count()).select_from(AiAnalysis).where(AiAnalysis.user_id == user.id)
    ) or 0
    sessions_completed = db.scalar(
        select(func.count())
        .select_from(ExerciseSession)
        .where(ExerciseSession.user_id == user.id, ExerciseSession.status == "completed")
    ) or 0
    exercise_count = db.scalar(select(func.count()).select_from(Exercise)) or 0

    return DashboardOut(
        recent_analyses=[AnalysisDetailOut.model_validate(a) for a in analysis_list],
        latest_analysis=AnalysisDetailOut.model_validate(latest) if latest else None,
        latest_recommendation=latest_rec,
        total_analyses=total_analyses,
        total_sessions_completed=sessions_completed,
        upcoming_sessions=upcoming,
        progress_entries=progress_list,
        exercise_count=exercise_count,
    )
