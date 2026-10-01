"""Admin-only endpoints for system management."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import DbDep, require_roles
from app.models import AiAnalysis, AuditLog, Exercise, ExerciseSession, User, XrayUpload

router = APIRouter(prefix="/admin", tags=["admin"])

AdminUser = Annotated[User, Depends(require_roles("admin"))]


# ---------- Schemas ----------

class AdminStatsOut(BaseModel):
    total_users: int
    total_analyses: int
    total_uploads: int
    total_exercises: int
    total_sessions: int
    users_by_role: dict[str, int]
    analyses_by_status: dict[str, int]


class UserListOut(BaseModel):
    users: list[dict]
    total: int


class UserUpdateIn(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class AuditLogOut(BaseModel):
    id: str
    user_id: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    ip_address: str | None
    details: dict | None
    created_at: str


class AuditLogListOut(BaseModel):
    logs: list[AuditLogOut]
    total: int


# ---------- Endpoints ----------

@router.get("/stats", response_model=AdminStatsOut)
def get_stats(_admin: AdminUser, db: DbDep) -> AdminStatsOut:
    total_users = db.scalar(select(func.count(User.id))) or 0
    total_analyses = db.scalar(select(func.count(AiAnalysis.id))) or 0
    total_uploads = db.scalar(select(func.count(XrayUpload.id))) or 0
    total_exercises = db.scalar(select(func.count(Exercise.id))) or 0
    total_sessions = db.scalar(select(func.count(ExerciseSession.id))) or 0

    # users by role
    role_rows = db.execute(select(User.role, func.count(User.id)).group_by(User.role)).all()
    users_by_role = {row[0]: row[1] for row in role_rows}

    # analyses by status
    status_rows = db.execute(select(AiAnalysis.status, func.count(AiAnalysis.id)).group_by(AiAnalysis.status)).all()
    analyses_by_status = {row[0]: row[1] for row in status_rows}

    return AdminStatsOut(
        total_users=total_users,
        total_analyses=total_analyses,
        total_uploads=total_uploads,
        total_exercises=total_ercises,
        total_sessions=total_sessions,
        users_by_role=users_by_role,
        analyses_by_status=analyses_by_status,
    )


@router.get("/users", response_model=UserListOut)
def list_users(
    _admin: AdminUser,
    db: DbDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> UserListOut:
    total = db.scalar(select(func.count(User.id))) or 0
    rows = db.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    ).scalars().all()
    users = [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in rows
    ]
    return UserListOut(users=users, total=total)


@router.patch("/users/{user_id}", response_model=dict)
def update_user(
    user_id: str,
    payload: UserUpdateIn,
    _admin: AdminUser,
    db: DbDep,
) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.role is not None:
        if payload.role not in ("patient", "clinician", "admin"):
            raise HTTPException(status_code=400, detail="Invalid role")
        user.role = payload.role

    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return {"id": user.id, "role": user.role, "is_active": user.is_active}


@router.delete("/users/{user_id}", response_model=dict)
def deactivate_user(
    user_id: str,
    _admin: AdminUser,
    db: DbDep,
) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    db.commit()
    return {"id": user.id, "message": "User deactivated"}


@router.get("/audit-logs", response_model=AuditLogListOut)
def list_audit_logs(
    _admin: AdminUser,
    db: DbDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user_id: str | None = Query(None),
) -> AuditLogListOut:
    stmt = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))

    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)

    total = db.scalar(count_stmt) or 0
    rows = db.execute(
        stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    ).scalars().all()

    logs = [
        AuditLogOut(
            id=log.id,
            user_id=log.user_id,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            ip_address=log.ip_address,
            details=log.details,
            created_at=log.created_at.isoformat(),
        )
        for log in rows
    ]
    return AuditLogListOut(logs=logs, total=total)
