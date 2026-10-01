"""Analysis endpoints — trigger, poll, and fetch AI reports."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbDep
from app.db.session import SessionLocal
from app.models import (
    AiAnalysis,
    RehabilitationRecommendation,
    XrayUpload,
)
from app.schemas import (
    AnalysisCreateIn,
    AnalysisDetailOut,
    AnalysisOut,
    ExerciseOut,
    MessageOut,
    RecommendationOut,
    ReportOut,
)
from app.services import analysis as analysis_service
from app.services import audit

router = APIRouter(prefix="/analyses", tags=["analyses"])


def _get_own_analysis(db: DbDep, user: CurrentUser, analysis_id: str) -> AiAnalysis:
    analysis = db.scalar(
        select(AiAnalysis)
        .where(AiAnalysis.id == analysis_id, AiAnalysis.user_id == user.id)
        .options(
            selectinload(AiAnalysis.regions),
            selectinload(AiAnalysis.upload),
            selectinload(AiAnalysis.recommendation),
        )
    )
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return analysis


def _run_analysis_background(analysis_id: str) -> None:
    db = SessionLocal()
    try:
        analysis = db.get(AiAnalysis, analysis_id)
        if not analysis:
            return
        upload = db.get(XrayUpload, analysis.upload_id)
        if not upload:
            return
        completed = analysis_service.run_analysis(
            db,
            upload=upload,
            analysis=analysis,
            affected_side=upload.affected_side or "right",
            affected_region=upload.affected_region or "wrist",
        )
        analysis_service.run_recommendation(db, completed)
    except Exception as exc:  # noqa: BLE001 — background task must never crash the worker
        import logging

        logging.getLogger("rehabx.analysis").exception("Background analysis %s failed", analysis_id)
        db.rollback()
        failed = db.get(AiAnalysis, analysis_id)
        if failed:
            failed.status = "failed"
            db.commit()
        raise exc
    finally:
        db.close()


@router.post("", response_model=AnalysisOut, status_code=status.HTTP_202_ACCEPTED)
def create_analysis(
    payload: AnalysisCreateIn,
    user: CurrentUser,
    db: DbDep,
    background: BackgroundTasks,
) -> AiAnalysis:
    upload = db.scalar(
        select(XrayUpload).where(XrayUpload.id == payload.upload_id, XrayUpload.user_id == user.id)
    )
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
    if upload.status == "processing":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An analysis is already in progress")

    # Create a placeholder row so the client can poll immediately.
    analysis = AiAnalysis(
        upload_id=upload.id,
        user_id=user.id,
        model_name="pending",
        model_version="pending",
        model_status="pending",
        prediction_label="pending",
        confidence=0.0,
        class_probabilities={},
        findings={},
        status="processing",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    upload.status = "processing"
    # Report-parsed facts take precedence over the request payload when present.
    parsed = upload.report_parsed or {}
    upload.affected_side = payload.affected_side or parsed.get("affected_side") or "right"
    upload.affected_region = payload.affected_region or parsed.get("affected_region") or "wrist"
    db.commit()

    audit.log(
        db,
        user_id=user.id,
        action="analysis.requested",
        entity_type="ai_analysis",
        entity_id=analysis.id,
        details={"upload_id": upload.id},
    )
    background.add_task(_run_analysis_background, analysis.id)
    return analysis


@router.get("/{analysis_id}", response_model=AnalysisDetailOut)
def get_analysis(analysis_id: str, user: CurrentUser, db: DbDep) -> AiAnalysis:
    return _get_own_analysis(db, user, analysis_id)


@router.get("/{analysis_id}/report", response_model=ReportOut)
def get_report(analysis_id: str, user: CurrentUser, db: DbDep) -> ReportOut:
    analysis = _get_own_analysis(db, user, analysis_id)
    if analysis.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Analysis is not complete (status: {analysis.status})",
        )
    rec = db.scalar(
        select(RehabilitationRecommendation).where(RehabilitationRecommendation.analysis_id == analysis.id)
    )
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not ready")

    report_text = analysis_service.build_report_text(analysis, rec)
    rec_out = RecommendationOut.model_validate(rec)
    raw_sections = rec.recommended_exercise_categories or []
    if raw_sections and all(isinstance(s.get("exercise_slugs"), list) for s in raw_sections):
        # Engine v2 sections carry their own scoped slug lists.
        resolved = analysis_service.resolve_section_exercises(db, raw_sections)
    else:
        resolved = analysis_service.resolve_category_exercises(
            db, [c.key for c in rec_out.recommended_exercise_categories]
        )
    rec_out = rec_out.model_copy(
        update={
            "recommended_exercise_categories": [
                c.model_copy(
                    update={"exercises": [ExerciseOut.model_validate(e) for e in resolved.get(c.key, [])]}
                )
                for c in rec_out.recommended_exercise_categories
            ]
        }
    )
    return ReportOut(
        upload_id=analysis.upload_id,
        analysis=AnalysisOut.model_validate(analysis),
        recommendation=rec_out,
        detected_regions=analysis.regions,
        report_text=report_text,
        disclaimer=rec.disclaimer,
    )


@router.delete("/{analysis_id}", response_model=MessageOut)
def delete_analysis(analysis_id: str, user: CurrentUser, db: DbDep) -> MessageOut:
    analysis = _get_own_analysis(db, user, analysis_id)
    db.delete(analysis)
    db.commit()
    return MessageOut(message="Analysis deleted")
