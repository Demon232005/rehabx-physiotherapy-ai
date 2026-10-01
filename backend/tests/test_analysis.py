"""Tests for the analysis flow (with a stubbed AI bridge) and reporting."""
from __future__ import annotations

import time

from test_uploads import VALID_PNG


def test_full_analysis_flow(client, auth_headers, uploaded_xray, mock_ai_result):
    upload_id = uploaded_xray

    resp = client.post(
        "/api/v1/analyses",
        json={"upload_id": upload_id, "affected_side": "right", "affected_region": "wrist"},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    analysis_id = resp.json()["id"]

    # Background task runs to completion under TestClient; poll until done.
    for _ in range(50):
        detail = client.get(f"/api/v1/analyses/{analysis_id}", headers=auth_headers).json()
        if detail["status"] == "completed":
            break
        time.sleep(0.05)
    assert detail["status"] == "completed"
    assert detail["prediction_label"] == "abnormal"
    assert detail["confidence"] == 0.83
    assert detail["model_status"] == "pretrained_backbone"
    assert len(detail["regions"]) == 2
    assert detail["findings"]["fracture_suspicion"] == 0.78

    # Recommendation should exist
    report = client.get(f"/api/v1/analyses/{analysis_id}/report", headers=auth_headers)
    assert report.status_code == 200
    data = report.json()
    assert data["recommendation"]["abnormality_category"] == "abnormal_fracture_suspicion"
    assert "clinician" in data["recommendation"]["rehab_focus"].lower()
    assert any("STOP" in w or "fracture" in w.lower() for w in data["recommendation"]["safety_warnings"])
    assert data["recommendation"]["recommended_exercise_categories"]
    # Every recommended category must resolve to concrete, startable exercises.
    for cat in data["recommendation"]["recommended_exercise_categories"]:
        assert cat["exercises"], f"category '{cat['key']}' resolved to no exercises"
        assert {"id", "slug", "name"} <= set(cat["exercises"][0])
    gliding = next(
        c for c in data["recommendation"]["recommended_exercise_categories"] if c["key"] == "gentle_finger_gliding"
    )
    assert gliding["exercises"][0]["slug"] == "finger-flexion"
    assert "disclaimer" in data["report_text"].lower()
    assert "HAND X-RAY AI REPORT" in data["report_text"]

    # Sessions can be created against the analysis
    ex = client.get("/api/v1/exercises", headers=auth_headers).json()[0]
    sresp = client.post(
        "/api/v1/sessions",
        json={"exercise_id": ex["id"], "analysis_id": analysis_id, "planned_reps": 10, "planned_sets": 3},
        headers=auth_headers,
    )
    assert sresp.status_code == 201
    session_id = sresp.json()["id"]

    # Complete a session
    up = client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"status": "completed", "completed_reps": 10, "completed_sets": 3, "pain_level": 1},
        headers=auth_headers,
    )
    assert up.status_code == 200
    assert up.json()["status"] == "completed"

    # Log progress
    presp = client.post(
        "/api/v1/progress",
        json={"analysis_id": analysis_id, "pain_level": 2, "self_reported_improvement": 40},
        headers=auth_headers,
    )
    assert presp.status_code == 201


def test_report_driven_analysis(client, auth_headers, mock_ai_result):
    upload_id = client.post(
        "/api/v1/uploads",
        files={"file": ("hand.png", VALID_PNG, "image/png")},
        data={
            "xray_report": "Fracture of the left distal radius. Mild comminution noted. No dislocation.",
            "affected_side": "right",
            "affected_region": "hand",
        },
        headers=auth_headers,
    ).json()["id"]

    upload = client.get(f"/api/v1/uploads/{upload_id}", headers=auth_headers).json()
    assert upload["affected_side"] == "left"
    assert upload["affected_region"] == "wrist"
    assert upload["report_parsed"]["severity"] == "mild"
    assert upload["report_parsed"]["condition"] == "fracture"

    # Payload omits side/region; the report decides.
    resp = client.post(
        "/api/v1/analyses", json={"upload_id": upload_id}, headers=auth_headers
    )
    assert resp.status_code == 202
    analysis_id = resp.json()["id"]

    for _ in range(50):
        detail = client.get(f"/api/v1/analyses/{analysis_id}", headers=auth_headers).json()
        if detail["status"] == "completed":
            break
        time.sleep(0.05)
    assert detail["status"] == "completed"
    assert detail["upload"]["affected_side"] == "left"
    assert detail["upload"]["affected_region"] == "wrist"
    report = detail["findings"]["report"]
    assert report["provided"] is True
    assert report["severity"] == "mild"
    assert report["condition"] == "fracture"
    assert report["affected_side"] == "left"

    data = client.get(f"/api/v1/analyses/{analysis_id}/report", headers=auth_headers).json()
    assert data["recommendation"]["affected_side"] == "left"
    assert "Report Severity: Mild" in data["report_text"]
    assert "Report Condition: Fracture" in data["report_text"]


def test_analysis_requires_ownership(client, auth_headers, mock_ai_result):
    client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "SecurePass123", "full_name": "Owner"},
    )
    owner_token = client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "SecurePass123"}
    ).json()["access_token"]

    upload_id = client.post(
        "/api/v1/uploads",
        files={"file": ("hand.png", VALID_PNG, "image/png")},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()["id"]

    # Another user cannot analyze the upload
    resp = client.post(
        "/api/v1/analyses",
        json={"upload_id": upload_id, "affected_side": "left", "affected_region": "hand"},
        headers=auth_headers,
    )
    assert resp.status_code == 404

def test_dashboard_aggregates(client, auth_headers, mock_ai_result, uploaded_xray):
    client.post(
        "/api/v1/analyses",
        json={"upload_id": uploaded_xray, "affected_side": "right", "affected_region": "wrist"},
        headers=auth_headers,
    )
    for _ in range(50):
        dash = client.get("/api/v1/dashboard", headers=auth_headers).json()
        if dash["total_analyses"] == 1 and dash["latest_analysis"] and dash["latest_analysis"]["status"] == "completed":
            break
        time.sleep(0.05)

    dash = client.get("/api/v1/dashboard", headers=auth_headers).json()
    assert dash["total_analyses"] == 1
    assert dash["latest_recommendation"] is not None
    assert dash["exercise_count"] >= 10
    assert dash["latest_analysis"]["model_name"] == "efficientnet_b0"
