"""Clinician-approved hand/wrist exercise library.

Data is stored as structured JSON in `knowledge_base/` so it can be
audited, versioned and replaced without touching code.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"


def _load(name: str) -> dict[str, Any]:
    with open(_KB_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def get_exercise_library() -> list[dict[str, Any]]:
    return _load("exercise_library.json")["exercises"]


def get_exercise_by_slug(slug: str) -> dict[str, Any] | None:
    for ex in get_exercise_library():
        if ex["slug"] == slug:
            return ex
    return None


def get_exercises_by_slugs(slugs: list[str]) -> list[dict[str, Any]]:
    lookup = {ex["slug"]: ex for ex in get_exercise_library()}
    return [lookup[s] for s in slugs if s in lookup]
