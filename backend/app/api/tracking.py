"""Exercise session and progress tracking endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbDep
from app.models import AiAnalysis, Exercise, ExerciseSession, Progress, RehabilitationRecommendation, XrayUpload
from app.schemas import (
    ExerciseSessionCreate,
    ExerciseSessionOut,
    ExerciseSessionUpdate,
    MessageOut,
    ProgressCreate,
    ProgressOut,
)
from app.services import audit

router = APIRouter(tags=["tracking"])


def _laterality_from_analysis(
    db: DbDep, user_id: str, analysis_id: str
) -> tuple[str | None, str | None, str | None]:
    """(side, region, structure) extracted from the report behind an analysis."""
    analysis = db.get(AiAnalysis, analysis_id)
    if not analysis or analysis.user_id != user_id:
        return None, None, None
    rec = db.scalar(
        select(RehabilitationRecommendation).where(
            RehabilitationRecommendation.analysis_id == analysis.id
        )
    )
    upload = db.get(XrayUpload, analysis.upload_id)
    extraction: dict = (rec.extraction if rec and rec.extraction else None) or (
        upload.report_parsed if upload and isinstance(upload.report_parsed, dict) else {}
    ) or {}
    side = extraction.get("affected_side") or (upload.affected_side if upload else None)
    region = extraction.get("affected_region") or (upload.affected_region if upload else None)
    structure = extraction.get("specific_structure") or extraction.get("sub_region")
    return side, region, structure


# ---------------- Exercise sessions ----------------
@router.post("/sessions", response_model=ExerciseSessionOut, status_code=201)
def create_session(payload: ExerciseSessionCreate, user: CurrentUser, db: DbDep) -> ExerciseSession:
    exercise = db.get(Exercise, payload.exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    side = region = structure = None
    if payload.analysis_id:
        side, region, structure = _laterality_from_analysis(db, user.id, payload.analysis_id)

    session = ExerciseSession(
        user_id=user.id,
        exercise_id=payload.exercise_id,
        analysis_id=payload.analysis_id,
        planned_reps=payload.planned_reps,
        planned_sets=payload.planned_sets,
        status="planned",
        affected_side=side,
        body_region=region,
        specific_structure=structure,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _with_exercise(db, session)


@router.get("/sessions", response_model=list[ExerciseSessionOut])
def list_sessions(user: CurrentUser, db: DbDep) -> list[ExerciseSessionOut]:
    sessions = db.scalars(
        select(ExerciseSession)
        .where(ExerciseSession.user_id == user.id)
        .options(selectinload(ExerciseSession.exercise))
        .order_by(ExerciseSession.created_at.desc())
    )
    return list(sessions)


@router.patch("/sessions/{session_id}", response_model=ExerciseSessionOut)
def update_session(
    session_id: str, payload: ExerciseSessionUpdate, user: CurrentUser, db: DbDep
) -> ExerciseSessionOut:
    session = db.scalar(
        select(ExerciseSession).where(ExerciseSession.id == session_id, ExerciseSession.user_id == user.id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        session.status = data["status"]
        if data["status"] == "completed" and not session.completed_at:
            session.completed_at = datetime.now(timezone.utc)
    for field in ("completed_reps", "completed_sets", "pain_level", "notes"):
        if field in data:
            setattr(session, field, data[field])
    db.commit()
    db.refresh(session)
    audit.log(db, user_id=user.id, action="session.updated", entity_type="exercise_sessions", entity_id=session.id)
    return _with_exercise(db, session)


def _with_exercise(db: DbDep, session: ExerciseSession) -> ExerciseSessionOut:
    session = db.scalar(
        select(ExerciseSession)
        .where(ExerciseSession.id == session.id)
        .options(selectinload(ExerciseSession.exercise))
    )
    return ExerciseSessionOut.model_validate(session)


# ---------------- Progress ----------------
@router.post("/progress", response_model=ProgressOut, status_code=201)
def create_progress(payload: ProgressCreate, user: CurrentUser, db: DbDep, response: Response) -> Progress:
    session_row: ExerciseSession | None = None
    if payload.exercise_session_id:
        # Auto-log path: the entry must reference one of THIS user's sessions
        # that actually completed — early exits never create progress data.
        session_row = db.scalar(
            select(ExerciseSession).where(
                ExerciseSession.id == payload.exercise_session_id,
                ExerciseSession.user_id == user.id,
            )
        )
        if not session_row:
            raise HTTPException(status_code=404, detail="Exercise session not found")
        if session_row.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Progress can only be logged for completed sessions",
            )
        # Idempotency guard: a session yields at most one progress entry,
        # even if the completion callback fires twice.
        existing = db.scalar(
            select(Progress).where(
                Progress.user_id == user.id,
                Progress.exercise_session_id == payload.exercise_session_id,
            )
        )
        if existing:
            response.status_code = status.HTTP_200_OK
            return existing

    entry = Progress(
        user_id=user.id,
        analysis_id=payload.analysis_id or (session_row.analysis_id if session_row else None),
        pain_level=payload.pain_level if payload.pain_level is not None else (session_row.pain_level if session_row else None),
        grip_strength_kg=payload.grip_strength_kg,
        range_of_motion_deg=payload.range_of_motion_deg,
        self_reported_improvement=payload.self_reported_improvement,
        notes=payload.notes,
        exercise_session_id=payload.exercise_session_id,
        form_score=payload.form_score,
        reps_completed=payload.reps_completed
        if payload.reps_completed is not None
        else (session_row.completed_reps if session_row else None),
        duration_seconds=payload.duration_seconds,
        source="session" if payload.exercise_session_id else payload.source,
        # Laterality snapshot (spec §18): progress inherits the injury the
        # session rehabilitates so trends can be reported per injury.
        affected_side=session_row.affected_side if session_row else None,
        body_region=session_row.body_region if session_row else None,
        specific_structure=session_row.specific_structure if session_row else None,
        date=session_row.completed_at.replace(tzinfo=None)
        if session_row and session_row.completed_at
        else datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    audit.log(db, user_id=user.id, action="progress.created", entity_type="progress", entity_id=entry.id)
    return entry


@router.get("/progress", response_model=list[ProgressOut])
def list_progress(user: CurrentUser, db: DbDep) -> list[Progress]:
    return list(
        db.scalars(select(Progress).where(Progress.user_id == user.id).order_by(Progress.date.desc()))
    )
