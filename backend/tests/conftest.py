"""Shared test fixtures.

Environment is configured BEFORE importing the app so settings are picked
up correctly. Tests use a temporary SQLite database and mock the AI
inference subprocess.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMPDIR = tempfile.mkdtemp(prefix="rehabx_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMPDIR}/test.db"
os.environ["STORAGE_DIR"] = f"{_TMPDIR}/storage"
os.environ["AUDIT_LOG_PATH"] = f"{_TMPDIR}/audit.log"
os.environ["DISABLE_AUDIT_FILE"] = "1"
os.environ["AI_INFERENCE_CLI"] = "python"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef"
os.environ["AI_INFERENCE_TIMEOUT_SECONDS"] = "30"
os.environ["RATE_LIMIT_ENABLED"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import analysis as analysis_service  # noqa: E402
from app.services import ai_client  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    import uuid

    email = f"patient-{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass123"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test Patient"},
    )
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def mock_ai_result(monkeypatch):
    """Replace the subprocess AI bridge with a deterministic stub.

    The stub returns the same structured shape the real AI CLI produces,
    so the full orchestration path is exercised without running PyTorch.
    """
    def _fake(image_path: str, **kwargs) -> dict:
        return {
            "model_name": "efficientnet_b0",
            "model_version": "test-fake-v1",
            "model_status": "pretrained_backbone",
            "prediction_label": "abnormal",
            "confidence": 0.83,
            "class_probabilities": {"normal": 0.17, "abnormal": 0.83},
            "findings": {
                "summary": "Focal high-intensity signal pattern consistent with possible bone disruption.",
                "fracture_suspicion": 0.78,
                "degenerative_changes": 0.12,
                "soft_tissue_swelling": 0.31,
                "degraded_input": False,
            },
            "preprocessing": {
                "resized_to": [512, 512],
                "clahe_applied": True,
                "normalization": "imagenet",
            },
            "detected_regions": [
                {"label": "wrist joint", "region_type": "joint",
                 "bbox": {"x": 120, "y": 180, "w": 90, "h": 70}, "confidence": 0.81,
                 "method": "unet"},
                {"label": "distal radius", "region_type": "bone",
                 "bbox": {"x": 110, "y": 230, "w": 80, "h": 120}, "confidence": 0.74,
                 "method": "classical_cv"},
            ],
        }

    monkeypatch.setattr(ai_client, "run_inference", _fake)
    return _fake


@pytest.fixture()
def uploaded_xray(client: TestClient, auth_headers: dict[str, str]) -> str:
    # A tiny valid PNG (1x1) — storage validation accepts it.
    import base64
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    resp = client.post(
        "/api/v1/uploads",
        files={"file": ("hand.png", png, "image/png")},
        data={"affected_side": "right", "affected_region": "wrist"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]
