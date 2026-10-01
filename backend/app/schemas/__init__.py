from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("password must contain an uppercase letter and a digit")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(ORMModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    created_at: datetime


# ---------- Uploads ----------
class UploadOut(ORMModel):
    id: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    image_width: int | None
    image_height: int | None
    affected_side: str | None
    affected_region: str | None
    xray_report: str | None
    report_parsed: dict[str, Any] | None
    status: str
    created_at: datetime


class UploadPreviewOut(BaseModel):
    id: str
    image_url: str  # short-lived signed URL, never a public X-ray URL


class ReportParsedOut(BaseModel):
    affected_side: str | None = None
    affected_region: str | None = None
    sub_region: str | None = None
    specific_structure: str | None = None
    severity: str | None = None
    condition: str | None = None
    condition_label: str | None = None
    summary: str = ""
    restrictions: list[dict[str, str]] = []
    findings: list[dict[str, Any]] = []
    recommended_region: str | None = None
    matched_terms: dict[str, Any] = {}
    confidence: dict[str, float] = {}
    source: str = "xray_report"


class ReportFileParsedOut(BaseModel):
    filename: str
    text: str
    parsed: ReportParsedOut


# ---------- Detected regions ----------
class DetectedRegionOut(ORMModel):
    id: str
    label: str
    region_type: str
    bbox_x: int | None
    bbox_y: int | None
    bbox_w: int | None
    bbox_h: int | None
    confidence: float
    detection_method: str


# ---------- Analysis ----------
class AnalysisOut(ORMModel):
    id: str
    upload_id: str
    model_name: str
    model_version: str
    model_status: str
    prediction_label: str
    confidence: float
    class_probabilities: dict[str, float]
    findings: dict[str, Any]
    preprocessing: dict[str, Any] | None
    analysis_duration_ms: int | None
    status: str
    created_at: datetime
    regions: list[DetectedRegionOut] = []


class AnalysisDetailOut(AnalysisOut):
    upload: UploadOut | None = None


class AnalysisCreateIn(BaseModel):
    upload_id: str
    # Manual override; the parsed report wins when these are omitted.
    affected_side: str | None = Field(default=None, pattern="^(left|right|bilateral)$")
    affected_region: str | None = Field(
        default=None,
        pattern="^(hand|wrist|fingers|thumb|palm|forearm|elbow|upper_arm|shoulder)$",
    )


# ---------- Exercises ----------
class ExerciseOut(ORMModel):
    id: str
    slug: str
    name: str
    description: str
    target_region: str
    movement_type: str
    starting_position: str
    required_movement: str
    contraindications: list[str]
    difficulty: str
    rep_range_min: int
    rep_range_max: int
    set_range_min: int
    set_range_max: int
    animation_placeholder: str | None
    # Upper-limb platform fields (null on legacy rows until reseeded)
    category: str | None = None
    tracking_mode: str | None = None  # hand|pose|hand+pose
    duration_minutes: int | None = None
    progression_level: int | None = None


class RecommendedCategoryOut(BaseModel):
    key: str
    label: str
    description: str
    # Concrete exercises resolved from the knowledge base at read time;
    # empty when none of the category's slugs exist in the library.
    exercises: list[ExerciseOut] = []
    # Report-driven sections (engine v2): the injury this section targets and
    # its safety verdict. Null on legacy image-driven category entries.
    target_side: str | None = None
    target_region: str | None = None
    sub_region: str | None = None
    specific_structure: str | None = None
    condition: str | None = None
    condition_label: str | None = None
    severity: str | None = None
    status: str = "ok"  # ok|needs_clarification|not_safe
    message: str | None = None


# ---------- Recommendations ----------
class RecommendationOut(ORMModel):
    id: str
    analysis_id: str
    rehab_focus: str
    affected_region: str
    affected_side: str
    abnormality_category: str
    focus_reasoning: list[str]
    recommended_exercise_categories: list[RecommendedCategoryOut]
    movement_requirements: list[str]
    repetition_guidance: dict[str, Any]
    session_structure: dict[str, Any]
    safety_warnings: list[str]
    disclaimer: str
    engine_version: str
    # Structured report extraction that produced this plan (engine v2).
    extraction: dict[str, Any] | None = None
    created_at: datetime


# ---------- Sessions / Progress ----------
class ExerciseSessionCreate(BaseModel):
    exercise_id: str
    analysis_id: str | None = None
    planned_reps: int | None = None
    planned_sets: int | None = None


class ExerciseSessionUpdate(BaseModel):
    status: str | None = None
    completed_reps: int | None = None
    completed_sets: int | None = None
    pain_level: int | None = Field(default=None, ge=0, le=10)
    notes: str | None = None
    completed_at: datetime | None = None


class ExerciseSessionOut(ORMModel):
    id: str
    exercise_id: str
    analysis_id: str | None
    planned_reps: int | None
    planned_sets: int | None
    completed_reps: int | None
    completed_sets: int | None
    status: str
    pain_level: int | None
    notes: str | None
    completed_at: datetime | None
    created_at: datetime
    exercise: ExerciseOut | None = None
    # Laterality snapshot from the driving report (spec §18).
    affected_side: str | None = None
    body_region: str | None = None
    specific_structure: str | None = None


class ProgressCreate(BaseModel):
    analysis_id: str | None = None
    pain_level: int | None = Field(default=None, ge=0, le=10)
    grip_strength_kg: float | None = Field(default=None, ge=0)
    range_of_motion_deg: float | None = Field(default=None, ge=0)
    self_reported_improvement: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = None
    # Auto-logging from a completed exercise session. When set, the entry is
    # linked to that session and deduplicated (one progress row per session).
    exercise_session_id: str | None = None
    form_score: int | None = Field(default=None, ge=0, le=100)
    reps_completed: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    source: str = Field(default="manual", pattern="^(manual|session)$")


class ProgressOut(ORMModel):
    id: str
    analysis_id: str | None
    date: datetime
    pain_level: int | None
    grip_strength_kg: float | None
    range_of_motion_deg: float | None
    self_reported_improvement: int | None
    notes: str | None
    exercise_session_id: str | None = None
    form_score: int | None = None
    reps_completed: int | None = None
    duration_seconds: int | None = None
    source: str = "manual"
    # Laterality snapshot copied from the session's driving report.
    affected_side: str | None = None
    body_region: str | None = None
    specific_structure: str | None = None


# ---------- Report ----------
class ReportOut(BaseModel):
    upload_id: str
    analysis: AnalysisOut
    recommendation: RecommendationOut
    detected_regions: list[DetectedRegionOut]
    report_text: str
    disclaimer: str


# ---------- Dashboard ----------
class DashboardOut(BaseModel):
    recent_analyses: list[AnalysisDetailOut]
    latest_analysis: AnalysisDetailOut | None = None
    latest_recommendation: RecommendationOut | None = None
    total_analyses: int
    total_sessions_completed: int
    upcoming_sessions: list[ExerciseSessionOut]
    progress_entries: list[ProgressOut]
    exercise_count: int


# ---------- Generic ----------
class MessageOut(BaseModel):
    message: str
