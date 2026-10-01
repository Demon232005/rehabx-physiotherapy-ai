"""Integrity tests for the rehabilitation knowledge base.

These guard against silent data rot: a typo in a slug or an orphaned
exercise would otherwise be dropped without any error at runtime.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from rehabilitation.knowledge_base import load_knowledge_base, validate_knowledge_base


def test_shipped_knowledge_base_is_valid():
    assert validate_knowledge_base() == []


def test_unknown_exercise_reference_is_detected():
    kb = load_knowledge_base()
    kb["exercise_categories"]["wrist_mobility"]["exercises"].append("does-not-exist")
    problems = validate_knowledge_base(kb)
    assert any("unknown exercise 'does-not-exist'" in p for p in problems)


def test_orphaned_exercise_is_detected(monkeypatch):
    kb = load_knowledge_base()
    # Simulate a library entry no category references.
    from rehabilitation import exercises as exercises_module

    original = exercises_module.get_exercise_library
    orphan = dict(original()[0], slug="orphan-move")
    monkeypatch.setattr(exercises_module, "get_exercise_library", lambda: [*original(), orphan])
    problems = validate_knowledge_base(kb)
    assert any("orphan-move" in p for p in problems)


def test_unknown_category_reference_is_detected():
    kb = load_knowledge_base()
    kb["abnormality_categories"]["normal"]["exercise_categories"].append("nope_category")
    problems = validate_knowledge_base(kb)
    assert any("unknown category 'nope_category'" in p for p in problems)


def test_load_validated_raises_on_invalid(monkeypatch):
    import rehabilitation.knowledge_base as kb_module

    kb = kb_module.load_knowledge_base()
    kb["regions"]["wrist"].pop("movement_requirements", None)
    monkeypatch.setattr(kb_module, "load_knowledge_base", lambda: kb)
    with pytest.raises(ValueError, match="Invalid knowledge base"):
        kb_module.load_validated_knowledge_base()
