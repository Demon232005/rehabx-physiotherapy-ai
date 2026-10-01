"""Tests for session → progress auto-logging.

Guarantees under test:
- only COMPLETED sessions can create a progress entry,
- one session yields exactly ONE progress entry (idempotent retries),
- values fall back to what the session already recorded,
- manual entries keep working and stay marked as source="manual".
"""
from __future__ import annotations

import uuid


def _make_session(client, auth_headers: dict[str, str]) -> str:
    ex = client.get("/api/v1/exercises", headers=auth_headers).json()[0]
    resp = client.post(
        "/api/v1/sessions",
        json={"exercise_id": ex["id"], "planned_reps": 10, "planned_sets": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _complete_session(client, auth_headers: dict[str, str], session_id: str):
    return client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"status": "completed", "completed_reps": 10, "completed_sets": 2, "pain_level": 2},
        headers=auth_headers,
    )


def test_completed_session_auto_logs_progress(client, auth_headers):
    session_id = _make_session(client, auth_headers)
    assert _complete_session(client, auth_headers, session_id).status_code == 200

    # LiveCoach sends the AI-measured values; pain/reps fall back to the
    # session record when not repeated here.
    first = client.post(
        "/api/v1/progress",
        json={
            "exercise_session_id": session_id,
            "range_of_motion_deg": 42.0,
            "form_score": 87,
            "duration_seconds": 324,
        },
        headers=auth_headers,
    )
    assert first.status_code == 201
    body = first.json()
    assert body["source"] == "session"
    assert body["exercise_session_id"] == session_id
    assert body["range_of_motion_deg"] == 42.0
    assert body["form_score"] == 87
    assert body["reps_completed"] == 10  # inherited from session.completed_reps
    assert body["pain_level"] == 2       # inherited from session.pain_level

    entries = client.get("/api/v1/progress", headers=auth_headers).json()
    assert len([e for e in entries if e["exercise_session_id"] == session_id]) == 1


def test_duplicate_completion_creates_only_one_entry(client, auth_headers):
    session_id = _make_session(client, auth_headers)
    _complete_session(client, auth_headers, session_id)
    payload = {"exercise_session_id": session_id, "form_score": 80}

    first = client.post("/api/v1/progress", json=payload, headers=auth_headers)
    second = client.post("/api/v1/progress", json=payload, headers=auth_headers)

    assert first.status_code == 201
    assert second.status_code == 200  # existing entry returned, not duplicated
    assert second.json()["id"] == first.json()["id"]

    entries = client.get("/api/v1/progress", headers=auth_headers).json()
    assert len([e for e in entries if e["exercise_session_id"] == session_id]) == 1


def test_progress_rejected_for_incomplete_session(client, auth_headers):
    session_id = _make_session(client, auth_headers)  # still "planned"
    resp = client.post(
        "/api/v1/progress",
        json={"exercise_session_id": session_id},
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_progress_rejected_for_skipped_session(client, auth_headers):
    session_id = _make_session(client, auth_headers)
    client.patch(
        f"/api/v1/sessions/{session_id}",
        json={"status": "skipped"},
        headers=auth_headers,
    )
    resp = client.post(
        "/api/v1/progress",
        json={"exercise_session_id": session_id},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    entries = client.get("/api/v1/progress", headers=auth_headers).json()
    assert entries == []


def test_progress_cannot_reference_foreign_session(client):
    def register_and_login(tag: str) -> dict[str, str]:
        email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePass123", "full_name": tag},
        )
        token = client.post(
            "/api/v1/auth/login", json={"email": email, "password": "SecurePass123"}
        ).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    owner, attacker = register_and_login("owner"), register_and_login("attacker")
    ex = client.get("/api/v1/exercises", headers=owner).json()[0]
    sid = client.post(
        "/api/v1/sessions", json={"exercise_id": ex["id"]}, headers=owner
    ).json()["id"]

    resp = client.post(
        "/api/v1/progress", json={"exercise_session_id": sid}, headers=attacker
    )
    assert resp.status_code == 404


def test_manual_progress_still_works_and_marked_manual(client, auth_headers):
    resp = client.post(
        "/api/v1/progress",
        json={"pain_level": 3, "grip_strength_kg": 18.5, "self_reported_improvement": 40},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "manual"
    assert body["exercise_session_id"] is None
    assert body["form_score"] is None
