"""Knowledge-base access helpers for the recommendation engine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"

_REQUIRED_EXERCISE_FIELDS = {
    "slug", "name", "description", "target_region", "movement_type",
    "starting_position", "required_movement", "contraindications",
    "difficulty", "rep_range", "set_range", "animation_placeholder",
}
_REQUIRED_REGION_FIELDS = {"label", "movement_requirements"}


def load_knowledge_base() -> dict[str, Any]:
    with open(_KB_DIR / "rehab_knowledge_base.json", encoding="utf-8") as fh:
        return json.load(fh)


def validate_knowledge_base(kb: dict[str, Any] | None = None) -> list[str]:
    """Validate internal consistency of the knowledge base.

    Returns a list of problems (empty means valid). Checks that:

    - every exercise referenced by a category exists in the library,
    - every library exercise is reachable from at least one category,
    - abnormality categories only reference existing exercise categories,
    - every abnormality category maps to at least one exercise category,
    - regions carry the fields the engine relies on.
    """
    from rehabilitation.exercises import get_exercise_library

    kb = kb if kb is not None else load_knowledge_base()
    problems: list[str] = []

    exercises = get_exercise_library()
    slugs = set()
    for ex in exercises:
        slug = ex.get("slug", "<missing>")
        missing_fields = _REQUIRED_EXERCISE_FIELDS - set(ex)
        if missing_fields:
            problems.append(f"exercise '{slug}' missing fields: {sorted(missing_fields)}")
        slugs.add(slug)

    categories = kb.get("exercise_categories", {})
    referenced: set[str] = set()
    for cat_key, cat in categories.items():
        for slug in cat.get("exercises", []):
            referenced.add(slug)
            if slug not in slugs:
                problems.append(
                    f"exercise category '{cat_key}' references unknown exercise '{slug}'"
                )

    for slug in sorted(slugs - referenced):
        problems.append(f"library exercise '{slug}' is not referenced by any category")

    abnormalities = kb.get("abnormality_categories", {})
    for abn_key, abn in abnormalities.items():
        refs = abn.get("exercise_categories", [])
        if not refs:
            problems.append(f"abnormality category '{abn_key}' has no exercise_categories")
        for cat_key in refs:
            if cat_key not in categories:
                problems.append(
                    f"abnormality category '{abn_key}' references unknown category '{cat_key}'"
                )

    for region_key, region in kb.get("regions", {}).items():
        missing_fields = _REQUIRED_REGION_FIELDS - set(region)
        if missing_fields:
            problems.append(f"region '{region_key}' missing fields: {sorted(missing_fields)}")

    return problems


def load_validated_knowledge_base() -> dict[str, Any]:
    """Load the knowledge base, raising if internally inconsistent."""
    kb = load_knowledge_base()
    problems = validate_knowledge_base(kb)
    if problems:
        raise ValueError("Invalid knowledge base: " + "; ".join(problems))
    return kb
