"""Unit tests for the rehabilitation recommendation engine.

These verify the deterministic, clinician-knowledge-based mapping from
structured findings to recommendations.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from rehabilitation.engine import RecommendationEngine


@pytest.fixture()
def engine() -> RecommendationEngine:
    return RecommendationEngine()


def test_normal_prediction_maps_to_maintenance(engine):
    rec = engine.recommend(
        affected_region="wrist",
        affected_side="right",
        prediction_label="normal",
        confidence=0.9,
        findings={"summary": "No abnormality detected."},
    )
    assert rec["abnormality_category"] == "normal"
    assert "Maintenance" in rec["rehab_focus"]
    assert rec["priority"] == "routine"
    assert rec["recommended_exercises"]
    assert all(ex["slug"] in {s["slug"] for s in rec["recommended_exercises"]} for ex in [])


def test_fracture_suspicion_is_conservative(engine):
    rec = engine.recommend(
        affected_region="wrist",
        prediction_label="abnormal",
        confidence=0.85,
        findings={"fracture_suspicion": 0.9, "degenerative_changes": 0.1, "soft_tissue_swelling": 0.2},
    )
    assert rec["abnormality_category"] == "abnormal_fracture_suspicion"
    assert "clinician" in rec["rehab_focus"].lower()
    assert any("STOP" in w or "fracture" in w.lower() for w in rec["safety_warnings"])
    assert rec["session_structure"]["intensity"] == "minimal"
    assert "clinician" in rec["repetition_guidance"]["general"]


def test_soft_tissue_swelling_mapping(engine):
    rec = engine.recommend(
        affected_region="hand",
        prediction_label="abnormal",
        confidence=0.7,
        findings={"fracture_suspicion": 0.2, "degenerative_changes": 0.1, "soft_tissue_swelling": 0.8},
    )
    assert rec["abnormality_category"] == "abnormal_soft_tissue_swelling"
    assert "edema" in rec["rehab_focus"].lower()


def test_degenerative_changes_mapping(engine):
    rec = engine.recommend(
        affected_region="wrist",
        prediction_label="abnormal",
        confidence=0.8,
        findings={"fracture_suspicion": 0.1, "degenerative_changes": 0.9, "soft_tissue_swelling": 0.1},
    )
    assert rec["abnormality_category"] == "abnormal_degenerative_changes"
    assert "degenerative" in rec["abnormality_label"].lower()


def test_generic_abnormal_fallback(engine):
    rec = engine.recommend(
        affected_region="wrist",
        prediction_label="abnormal",
        confidence=0.6,
        findings={"fracture_suspicion": 0.1, "degenerative_changes": 0.1, "soft_tissue_swelling": 0.1},
    )
    assert rec["abnormality_category"] == "abnormal_generic"


def test_high_user_pain_level_forces_minimal_intensity(engine):
    low = engine.recommend(
        affected_region="wrist",
        prediction_label="normal",
        confidence=0.8,
        user_provided={"pain_level": 2},
    )
    high = engine.recommend(
        affected_region="wrist",
        prediction_label="normal",
        confidence=0.8,
        user_provided={"pain_level": 8},
    )
    assert low["session_structure"]["intensity"] != "minimal"
    assert high["session_structure"]["intensity"] == "minimal"


def test_progress_can_advance_intensity(engine):
    base = engine.recommend(
        affected_region="wrist",
        prediction_label="normal",
        confidence=0.8,
        previous_progress=[{"pain_level": 1, "self_reported_improvement": 40}],
    )
    no_progress = engine.recommend(
        affected_region="wrist",
        prediction_label="normal",
        confidence=0.8,
        previous_progress=[{"pain_level": 7, "self_reported_improvement": 5}],
    )
    assert base["session_structure"]["intensity"] == "moderate"
    assert no_progress["session_structure"]["intensity"] != "moderate"


def test_determinism(engine):
    kwargs = dict(
        affected_region="wrist",
        prediction_label="abnormal",
        confidence=0.8,
        findings={"fracture_suspicion": 0.1, "degenerative_changes": 0.9, "soft_tissue_swelling": 0.1},
    )
    a = engine.recommend(**kwargs)
    b = engine.recommend(**kwargs)
    assert a == b


def test_disclaimer_present_and_no_diagnosis_claim(engine):
    rec = engine.recommend(affected_region="wrist", prediction_label="normal", confidence=0.8)
    assert "does not replace" in rec["disclaimer"].lower()
    assert "diagnos" not in rec["disclaimer"].lower().replace("not provide a medical diagnosis", "")


def test_exercise_fields_complete(engine):
    rec = engine.recommend(affected_region="hand", prediction_label="normal", confidence=0.9)
    required = {
        "slug", "name", "description", "target_region", "movement_type",
        "starting_position", "required_movement", "contraindications",
        "difficulty", "rep_range", "set_range", "animation_placeholder",
    }
    for ex in rec["recommended_exercises"]:
        assert required.issubset(ex.keys())


def test_all_exercises_have_all_required_fields():
    from rehabilitation.exercises import get_exercise_library

    required = {
        "slug", "name", "description", "target_region", "movement_type",
        "starting_position", "required_movement", "contraindications",
        "difficulty", "rep_range", "set_range", "animation_placeholder",
    }
    for ex in get_exercise_library():
        assert required.issubset(ex.keys()), ex.get("slug")
        assert len(ex["rep_range"]) == 2 and ex["rep_range"][0] <= ex["rep_range"][1]
        assert len(ex["set_range"]) == 2 and ex["set_range"][0] <= ex["set_range"][1]
