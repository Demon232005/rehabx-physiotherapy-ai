"""Exercise library endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbDep
from app.models import Exercise
from app.schemas import ExerciseOut

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("", response_model=list[ExerciseOut])
def list_exercises(
    db: DbDep,
    region: str | None = None,
    category: str | None = None,
    search: str | None = None,
) -> list[Exercise]:
    """List active exercises with optional upper-limb filters.

    region / category filter on exact values; search does a case-insensitive
    substring match over name + description.
    """
    query = select(Exercise).where(Exercise.is_active.is_(True))
    if region:
        query = query.where(Exercise.target_region == region.lower())
    if category:
        query = query.where(Exercise.category == category.lower())
    if search:
        term = f"%{search.strip().lower()}%"
        query = query.where(
            (Exercise.name.ilike(term)) | (Exercise.description.ilike(term))
        )
    return list(db.scalars(query.order_by(Exercise.target_region, Exercise.name)))


@router.get("/{slug}", response_model=ExerciseOut)
def get_exercise(slug: str, db: DbDep) -> Exercise:
    exercise = db.scalar(select(Exercise).where(Exercise.slug == slug))
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise
