"""Tests for secure upload validation and preview access."""
from __future__ import annotations

import base64
import io

from app.services import storage

VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_validate_image_accepts_real_png():
    ext, (w, h) = storage.validate_image(VALID_PNG)
    assert ext == ".png"
    assert (w, h) == (1, 1)


def test_validate_image_rejects_renamed_text():
    fake = b"this is not an image but has a png extension"
    try:
        storage.validate_image(fake)
        assert False, "should have raised"
    except ValueError as exc:
        assert "not a valid image" in str(exc)


def test_validate_image_rejects_oversize(monkeypatch):
    monkeypatch.setattr(storage.get_settings(), "max_upload_bytes", 50)
    try:
        storage.validate_image(VALID_PNG + b"x" * 200)
        assert False, "should have raised"
    except ValueError as exc:
        assert "maximum upload size" in str(exc)


def test_reject_invalid_side_and_region(client, auth_headers):
    resp = client.post(
        "/api/v1/uploads",
        files={"file": ("hand.png", VALID_PNG, "image/png")},
        data={"affected_side": "top", "affected_region": "wrist"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_upload_and_preview_require_ownership(client, auth_headers):
    # Create second user
    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "SecurePass123", "full_name": "Other"},
    )
    other = client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "SecurePass123"}
    ).json()["access_token"]

    upload_id = client.post(
        "/api/v1/uploads",
        files={"file": ("hand.png", VALID_PNG, "image/png")},
        data={"affected_side": "right", "affected_region": "hand"},
        headers=auth_headers,
    ).json()["id"]

    # Owner can fetch image
    img = client.get(f"/api/v1/uploads/{upload_id}/image", headers=auth_headers)
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/png"

    # Other user cannot
    img_other = client.get(
        f"/api/v1/uploads/{upload_id}/image", headers={"Authorization": f"Bearer {other}"}
    )
    assert img_other.status_code == 404

    # Anonymous cannot
    assert client.get(f"/api/v1/uploads/{upload_id}/image").status_code == 401


def test_upload_rejects_non_image_content(client, auth_headers):
    resp = client.post(
        "/api/v1/uploads",
        files={"file": ("fake.png", b"<html>not an image</html>", "image/png")},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_parse_report_file_text(client, auth_headers):
    resp = client.post(
        "/api/v1/uploads/parse-report-file",
        files={"report_file": ("report.txt", "Fracture of the left distal radius.".encode("utf-8"), "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "left" in data["text"]
    assert data["parsed"]["affected_side"] == "left"
    assert data["parsed"]["condition"] == "fracture"


def test_upload_with_report_file_overrides_side(client, auth_headers):
    resp = client.post(
        "/api/v1/uploads",
        files={"file": ("hand.png", VALID_PNG, "image/png")},
        data={
            "affected_side": "right",
            "affected_region": "hand",
            "xray_report": "Severely displaced fracture of the left wrist.",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    upload = resp.json()
    assert upload["affected_side"] == "left"
    assert upload["affected_region"] == "wrist"
    assert upload["report_parsed"]["severity"] == "severe"
    assert upload["report_parsed"]["condition"] == "displaced_fracture"


def test_upload_rejects_bad_report_file_type(client, auth_headers):
    resp = client.post(
        "/api/v1/uploads",
        files={
            "file": ("hand.png", VALID_PNG, "image/png"),
            "report_file": ("report.exe", b"MZ\x90\x00", "application/octet-stream"),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_report_only_upload_stores_and_serves_file(client, auth_headers):
    report = b"X-ray report: Fracture of the left distal radius. Moderate severity."
    resp = client.post(
        "/api/v1/uploads",
        files={"report_file": ("report.txt", report, "text/plain")},
        data={"affected_side": "left", "affected_region": "wrist"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    upload_id = resp.json()["id"]

    # Report text was extracted and stored.
    assert "distal radius" in (resp.json().get("xray_report") or "")

    # Original file is served back to the owner.
    got = client.get(f"/api/v1/uploads/{upload_id}/report-file", headers=auth_headers)
    assert got.status_code == 200
    assert got.content == report
    assert "text/plain" in got.headers["content-type"]
    assert "report.txt" in got.headers.get("content-disposition", "")

    # Image endpoints return 404 for report-only uploads.
    assert (
        client.get(f"/api/v1/uploads/{upload_id}/image", headers=auth_headers).status_code == 404
    )


def test_report_only_upload_requires_report(client, auth_headers):
    resp = client.post(
        "/api/v1/uploads",
        data={"affected_side": "right", "affected_region": "wrist"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_report_file_saved_alongside_image(client, auth_headers):
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    resp = client.post(
        "/api/v1/uploads",
        files={
            "file": ("hand.png", png, "image/png"),
            "report_file": ("note.txt", b"Mild swelling of the right wrist.", "text/plain"),
        },
        data={"affected_side": "right", "affected_region": "wrist"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    upload_id = resp.json()["id"]
    got = client.get(f"/api/v1/uploads/{upload_id}/report-file", headers=auth_headers)
    assert got.status_code == 200
    assert got.content == b"Mild swelling of the right wrist."
