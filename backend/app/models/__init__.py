from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="patient")  # patient|clinician|admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, server_default=func.now())

    uploads: Mapped[list["XrayUpload"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class XrayUpload(Base):
    __tablename__ = "xray_uploads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(nullable=False)
    image_width: Mapped[int | None] = mapped_column(nullable=True)
    image_height: Mapped[int | None] = mapped_column(nullable=True)
    affected_side: Mapped[str | None] = mapped_column(String(16), nullable=True)  # left|right
    affected_region: Mapped[str | None] = mapped_column(String(64), nullable=True)  # hand|wrist|fingers
    xray_report: Mapped[str | None] = mapped_column(Text, nullable=True)  # patient-supplied X-ray report text
    report_parsed: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # parsed from xray_report
    report_file_key: Mapped[str | None] = mapped_column(String(255), nullable=True)  # stored original report file
    report_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # original filename of the report file
    status: Mapped[str] = mapped_column(String(32), default="uploaded")  # uploaded|processing|completed|failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, server_default=func.now())

    owner: Mapped["User"] = relationship(back_populates="uploads")
    analyses: Mapped[list["AiAnalysis"]] = relationship(back_populates="upload", cascade="all, delete-orphan")


class AiAnalysis(Base):
    __tablename__ = "ai_analysis"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    upload_id: Mapped[str] = mapped_column(ForeignKey("xray_uploads.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)

    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_status: Mapped[str] = mapped_column(String(64), nullable=False)  # fine_tuned|pretrained_backbone

    prediction_label: Mapped[str] = mapped_column(String(32), nullable=False)  # normal|abnormal
    confidence: Mapped[float] = mapped_column(nullable=False)
    class_probabilities: Mapped[dict] = mapped_column(JSON, nullable=False)
    findings: Mapped[dict] = mapped_column(JSON, nullable=False)
    preprocessing: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis_duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, server_default=func.now())

    upload: Mapped["XrayUpload"] = relationship(back_populates="analyses")
    regions: Mapped[list["DetectedRegion"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")
    recommendation: Mapped["RehabilitationRecommendation | None"] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", uselist=False
    )


class DetectedRegion(Base):
    __tablename__ = "detected_regions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("ai_analysis.id"), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    region_type: Mapped[str] = mapped_column(String(32), nullable=False)  # bone|joint|background
    bbox_x: Mapped[int | None] = mapped_column(nullable=True)
    bbox_y: Mapped[int | None] = mapped_column(nullable=True)
    bbox_w: Mapped[int | None] = mapped_column(nullable=True)
    bbox_h: Mapped[int | None] = mapped_column(nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.0)
    detection_method: Mapped[str] = mapped_column(String(64), default="classical_cv")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, server_default=func.now())

    analysis: Mapped["AiAnalysis"] = relationship(back_populates="regions")


class RehabilitationRecommendation(Base):
    __tablename__ = "rehabilitation_recommendations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("ai_analysis.id"), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    upload_id: Mapped[str] = mapped_column(ForeignKey("xray_uploads.id"), index=True, nullable=False)

    rehab_focus: Mapped[str] = mapped_column(String(255), nullable=False)
    affected_region: Mapped[str] = mapped_column(String(64), nullable=False)
    affected_side: Mapped[str] = mapped_column(String(16), nullable=False, default="right")
    abnormality_category: Mapped[str] = mapped_column(String(64), nullable=False)
    focus_reasoning: Mapped[dict] = mapped_column(JSON, nullable=False)
    recommended_exercise_categories: Mapped[list] = mapped_column(JSON, nullable=False)
    movement_requirements: Mapped[list] = mapped_column(JSON, nullable=False)
    repetition_guidance: Mapped[dict] = mapped_column(JSON, nullable=False)
    session_structure: Mapped[dict] = mapped_column(JSON, nullable=False)
    safety_warnings: Mapped[list] = mapped_column(JSON, nullable=False)
    disclaimer: Mapped[str] = mapped_column(nullable=False)
    engine_version: Mapped[str] = mapped_column(String(16), default="1.0.0")
    # Structured report extraction (side/region/structure/condition/restrictions)
    # that drove this plan; null for legacy image-only recommendations.
    extraction: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, server_default=func.now())

    analysis: Mapped["AiAnalysis"] = relationship(back_populates="recommendation")


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    target_region: Mapped[str] = mapped_column(String(64), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(64), nullable=False)
    starting_position: Mapped[str] = mapped_column(nullable=False)
    required_movement: Mapped[str] = mapped_column(nullable=False)
    contraindications: Mapped[list] = mapped_column(JSON, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), default="beginner")
    rep_range_min: Mapped[int] = mapped_column(default=8)
    rep_range_max: Mapped[int] = mapped_column(default=12)
    set_range_min: Mapped[int] = mapped_column(default=2)
    set_range_max: Mapped[int] = mapped_column(default=3)
    animation_placeholder: Mapped[str | None] = mapped_column(nullable=True)  # URL/path
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, server_default=func.now())
    # Upper-limb platform fields (nullable so legacy rows remain valid):
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)  # mobility|stretching|strengthening|recovery
    tracking_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)  # hand|pose|hand+pose
    duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    progression_level: Mapped[int | None] = mapped_column(nullable=True)


class ExerciseSession(Base):
    __tablename__ = "exercise_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"), index=True, nullable=False)
    analysis_id: Mapped[str | None] = mapped_column(ForeignKey("ai_analysis.id"), nullable=True)
    planned_reps: Mapped[int | None] = mapped_column(nullable=True)
    planned_sets: Mapped[int | None] = mapped_column(nullable=True)
    completed_reps: Mapped[int | None] = mapped_column(nullable=True)
    completed_sets: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="planned")  # planned|in_progress|completed|skipped
    pain_level: Mapped[int | None] = mapped_column(nullable=True)  # 0-10
    notes: Mapped[str | None] = mapped_column(nullable=True)
    scheduled_date: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Laterality snapshot from the driving report (spec §18): the injury this
    # session rehabilitates, kept denormalised for progress reporting.
    affected_side: Mapped[str | None] = mapped_column(String(16), nullable=True)
    body_region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    specific_structure: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, server_default=func.now())

    exercise: Mapped["Exercise"] = relationship(lazy="selectin")


class Progress(Base):
    __tablename__ = "progress"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    analysis_id: Mapped[str | None] = mapped_column(ForeignKey("ai_analysis.id"), nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    pain_level: Mapped[int | None] = mapped_column(nullable=True)  # 0-10
    grip_strength_kg: Mapped[float | None] = mapped_column(nullable=True)
    range_of_motion_deg: Mapped[float | None] = mapped_column(nullable=True)  # AI-measured or goniometer
    self_reported_improvement: Mapped[int | None] = mapped_column(nullable=True)  # 0-100
    notes: Mapped[str | None] = mapped_column(nullable=True)
    # Auto-logged from a completed LiveCoach session (source="session").
    exercise_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("exercise_sessions.id"), index=True, nullable=True
    )
    form_score: Mapped[int | None] = mapped_column(nullable=True)  # 0-100 AI form percentage
    reps_completed: Mapped[int | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual|session
    # Laterality snapshot copied from the session's driving report (spec §18).
    affected_side: Mapped[str | None] = mapped_column(String(16), nullable=True)
    body_region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    specific_structure: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, server_default=func.now())

