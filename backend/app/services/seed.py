"""Seeds reference data (exercise library) from the rehabilitation package."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Exercise


def seed_reference_data(db: Session) -> None:
    try:
        from rehabilitation.exercises import get_exercise_library
    except ImportError:
        # rehabilitation package not installed / not on path — skip seeding.
        return

    from sqlalchemy import func, select

    existing = set(db.scalars(select(Exercise.slug)).all())
    total = db.scalar(select(func.count()).select_from(Exercise)) or 0
    if total and total == len(existing) and not any(
        ex["slug"] not in existing for ex in get_exercise_library()
    ):
        return

    for ex in get_exercise_library():
        if ex["slug"] in existing:
            continue
        db.add(
            Exercise(
                slug=ex["slug"],
                name=ex["name"],
                description=ex["description"],
                target_region=ex["target_region"],
                movement_type=ex["movement_type"],
                starting_position=ex["starting_position"],
                required_movement=ex["required_movement"],
                contraindications=ex.get("contraindications", []),
                difficulty=ex.get("difficulty", "beginner"),
                rep_range_min=ex["rep_range"][0],
                rep_range_max=ex["rep_range"][1],
                set_range_min=ex["set_range"][0],
                set_range_max=ex["set_range"][1],
                animation_placeholder=ex.get("animation_placeholder"),
                category=ex.get("category"),
                tracking_mode=ex.get("tracking_mode"),
                duration_minutes=ex.get("duration_min"),
                progression_level=ex.get("progression_level"),
            )
        )
    db.commit()
