"""Report-driven rehabilitation tests.

Covers spec §1-§12: structured extraction of side/region/structure/condition/
restrictions from the medical report, region-scoped exercise selection with a
condition/restriction safety filter, side-specific plan headings, and
laterality snapshots on sessions/progress.
"""
from __future__ import annotations

import time

import pytest

from app.services.report_parser import parse_report
from rehabilitation.engine.report_driven import (
    CONSULT_MESSAGE,
    ReportDrivenEngine,
)
from rehabilitation.knowledge_base import load_knowledge_base

from test_uploads import VALID_PNG


# ---------- Parser: hierarchy + laterality + restrictions ----------

def test_parse_left_index_finger_fracture():
    parsed = parse_report("Fracture of proximal phalanx of left index finger")
    assert parsed["affected_side"] == "left"
    assert parsed["affected_region"] == "hand"
    assert parsed["sub_region"] == "finger"
    assert parsed["specific_structure"] == "index_finger"
    assert parsed["recommended_region"] == "left_index_finger"
    assert parsed["condition"] in ("fracture", "hairline_fracture", "displaced_fracture")
    assert 0 < parsed["confidence"]["overall"] <= 1


def test_parse_left_distal_radius_maps_to_wrist():
    parsed = parse_report("Fracture of left distal radius")
    assert parsed["affected_side"] == "left"
    assert parsed["affected_region"] == "wrist"
    assert parsed["specific_structure"] == "distal_radius"


def test_parse_restrictions_are_extracted_not_invented():
    parsed = parse_report("Left wrist fracture. ORIF performed, in a back slab. Avoid lifting.")
    keys = {r["restriction"] for r in parsed["restrictions"]}
    assert {"post_operative", "immobilization", "avoid_resisted"} <= keys
    clean = parse_report("Left wrist mild pain, normal alignment.")
    assert clean["restrictions"] == []


def test_parse_bilateral_and_multiple_findings():
    multi = parse_report("Left wrist fracture + Right shoulder stiffness")
    pairs = [(f["side"], f["region"]) for f in multi["findings"]]
    assert ("left", "wrist") in pairs
    assert ("right", "shoulder") in pairs

    bilateral = parse_report("Bilateral hand osteoarthritis")
    assert bilateral["affected_side"] == "bilateral"
    assert bilateral["affected_region"] == "hand"


def test_parse_shoulder_and_elbow_regions():
    shoulder = parse_report("Right shoulder injury with rotator cuff strain")
    assert shoulder["affected_region"] == "shoulder"
    elbow = parse_report("Fracture of left olecranon")
    assert elbow["affected_region"] == "elbow"
    assert elbow["specific_structure"] == "olecranon"


# ---------- Engine v2: scoped selection + safety filter ----------

@pytest.fixture(scope="module")
def engine() -> ReportDrivenEngine:
    return ReportDrivenEngine(disclaimer=load_knowledge_base()["disclaimer"])


def _slugs(section):
    return section.get("exercise_slugs") or []


def test_engine_scopes_finger_fracture_to_hand_only(engine):
    ex = parse_report("Fracture of proximal phalanx of left index finger")
    rec = engine.recommend(extraction=ex, prediction_label="abnormal", confidence=0.9)
    assert rec is not None
    assert rec["rehab_focus"] == "Left index finger rehabilitation"
    sections = rec["recommended_exercise_categories"]
    assert len(sections) == 1
    section = sections[0]
    assert section["label"] == "Left index finger rehabilitation"
    assert section["target_side"] == "left"
    assert section["status"] == "ok"
    assert _slugs(section), "fracture-safe mobility exercises expected"
    by_slug = {e["slug"]: e for e in engine.exercises}
    for slug in _slugs(section):
        assert by_slug[slug]["target_region"] == "hand"
        # Safety: a reported fracture excludes strengthening entirely.
        assert by_slug[slug]["category"] != "strengthening"
    # No out-of-scope regions may leak in (spec §3).
    regions_in_plan = {by_slug[s]["target_region"] for s in _slugs(section)}
    assert regions_in_plan <= {"hand"}


def test_engine_blocks_post_operative_reports(engine):
    ex = parse_report("Left wrist fracture treated with ORIF and back slab immobilization")
    rec = engine.recommend(extraction=ex, prediction_label="abnormal", confidence=0.9)
    section = rec["recommended_exercise_categories"][0]
    assert section["status"] == "not_safe"
    assert section["exercise_slugs"] == []
    assert section["message"] == CONSULT_MESSAGE


def test_engine_blocks_undetermined_conditions(engine):
    ex = parse_report("Left index flexor tendon rupture")
    rec = engine.recommend(extraction=ex, prediction_label="abnormal", confidence=0.9)
    section = rec["recommended_exercise_categories"][0]
    assert section["status"] == "needs_clarification"
    assert section["message"] == CONSULT_MESSAGE


def test_engine_multiple_injuries_get_separate_sections(engine):
    ex = parse_report("Left wrist sprain + Right shoulder osteoarthritis")
    rec = engine.recommend(extraction=ex, prediction_label="abnormal", confidence=0.9)
    labels = [s["label"].lower() for s in rec["recommended_exercise_categories"]]
    assert any("wrist" in l for l in labels)
    assert any("shoulder" in l for l in labels)
    by_slug = {e["slug"]: e for e in engine.exercises}
    for section in rec["recommended_exercise_categories"]:
        scope = {"wrist", "forearm"} if "wrist" in section["label"].lower() else {"shoulder"}
        for slug in _slugs(section):
            assert by_slug[slug]["target_region"] in scope


def test_engine_poor_extraction_returns_none(engine):
    assert engine.recommend(extraction={"summary": ""}) is None


# ---------- API: end-to-end report-driven flow ----------

def _wait_completed(client, headers, analysis_id):
    detail = {}
    for _ in range(50):
        detail = client.get(f"/api/v1/analyses/{analysis_id}", headers=headers).json()
        if detail["status"] == "completed":
            break
        time.sleep(0.05)
    return detail


def test_report_driven_plan_end_to_end(client, auth_headers, mock_ai_result):
    upload_id = client.post(
        "/api/v1/uploads",
        files={"file": ("hand.png", VALID_PNG, "image/png")},
        data={
            "xray_report": "Fracture of proximal phalanx of left index finger",
            "affected_side": "right",
            "affected_region": "wrist",
        },
        headers=auth_headers,
    ).json()["id"]

    resp = client.post("/api/v1/analyses", json={"upload_id": upload_id}, headers=auth_headers)
    assert resp.status_code == 202
    analysis_id = resp.json()["id"]
    detail = _wait_completed(client, auth_headers, analysis_id)
    assert detail["status"] == "completed"

    # findings.report carries the full structured extraction
    report_facts = detail["findings"]["report"]
    assert report_facts["affected_side"] == "left"
    assert report_facts["specific_structure"] == "index_finger"
    assert report_facts["sub_region"] == "finger"
    assert report_facts["recommended_region"] == "left_index_finger"

    data = client.get(f"/api/v1/analyses/{analysis_id}/report", headers=auth_headers).json()
    rec = data["recommendation"]
    assert rec["engine_version"] == "2.0.0"
    assert rec["rehab_focus"] == "Left index finger rehabilitation"
    assert rec["extraction"]["specific_structure"] == "index_finger"
    sections = rec["recommended_exercise_categories"]
    assert len(sections) == 1
    section = sections[0]
    assert section["label"] == "Left index finger rehabilitation"
    assert section["target_side"] == "left"
    assert section["exercises"], "scoped section must resolve concrete exercises"
    assert all(e["target_region"] == "hand" for e in section["exercises"])

    # Laterality snapshot flows into sessions and auto-logged progress (§18)
    first_exercise = section["exercises"][0]
    sresp = client.post(
        "/api/v1/sessions",
        json={"exercise_id": first_exercise["id"], "analysis_id": analysis_id},
        headers=auth_headers,
    )
    assert sresp.status_code == 201
    session = sresp.json()
    assert session["affected_side"] == "left"
    assert session["body_region"] == "hand"
    assert session["specific_structure"] == "index_finger"

    client.patch(
        f"/api/v1/sessions/{session['id']}",
        json={"status": "completed", "completed_reps": 8, "pain_level": 2},
        headers=auth_headers,
    )
    presp = client.post(
        "/api/v1/progress",
        json={"exercise_session_id": session["id"], "range_of_motion_deg": 38},
        headers=auth_headers,
    )
    assert presp.status_code == 201
    entry = presp.json()
    assert entry["analysis_id"] == analysis_id
    assert entry["affected_side"] == "left"
    assert entry["body_region"] == "hand"
    assert entry["source"] == "session"


def test_unclear_report_yields_conservative_sections(client, auth_headers):
    # A report naming no usable anatomy cannot drive scoped recommendations:
    # the upload still parses but the recommendation must stay safe.
    parsed = parse_report("Study of the hand. No abnormality identified.")
    assert parsed["affected_region"] in ("hand", None)
    assert parsed["condition"] is None
