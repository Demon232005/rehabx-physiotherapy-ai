"""Tests for authentication and security utilities."""
from __future__ import annotations

from app.core.security import create_access_token, decode_token, hash_password, verify_password


def test_password_hashing_roundtrip():
    hashed = hash_password("MySecurePass123")
    assert hashed != "MySecurePass123"
    assert verify_password("MySecurePass123", hashed)
    assert not verify_password("wrong", hashed)


def test_password_hash_is_unique_per_call():
    assert hash_password("MySecurePass123") != hash_password("MySecurePass123")


def test_jwt_roundtrip():
    token = create_access_token("user-123", extra={"role": "patient"})
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "patient"


def test_weak_password_rejected(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "short", "full_name": "Weak"},
    )
    assert resp.status_code == 422


def test_register_and_login_flow(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "flow@example.com", "password": "SecurePass123", "full_name": "Flow User"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "flow@example.com"

    bad = client.post("/api/v1/auth/login", json={"email": "flow@example.com", "password": "nope"})
    assert bad.status_code == 401

    good = client.post("/api/v1/auth/login", json={"email": "flow@example.com", "password": "SecurePass123"})
    assert good.status_code == 200
    assert good.json()["token_type"] == "bearer"


def test_duplicate_registration_rejected(client):
    payload = {"email": "dup@example.com", "password": "SecurePass123", "full_name": "Dup"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_password_reset_request_sends_email(client, monkeypatch):
    import app.api.auth as auth_module

    sent: list[tuple[str, str]] = []

    def _fake(to: str, reset_token: str) -> bool:
        sent.append((to, reset_token))
        return True

    monkeypatch.setattr(auth_module, "send_password_reset_email", _fake)
    client.post(
        "/api/v1/auth/register",
        json={"email": "resetme@example.com", "password": "SecurePass123", "full_name": "Reset Me"},
    )
    resp = client.post("/api/v1/auth/password-reset/request", json={"email": "resetme@example.com"})
    assert resp.status_code == 200
    assert len(sent) == 1
    assert sent[0][0] == "resetme@example.com"
    assert sent[0][1]  # a token was produced


def test_password_reset_unknown_email_stays_generic(client, monkeypatch):
    import app.api.auth as auth_module

    called: list[str] = []
    monkeypatch.setattr(auth_module, "send_password_reset_email", lambda to, t: called.append(to))
    resp = client.post("/api/v1/auth/password-reset/request", json={"email": "ghost@example.com"})
    assert resp.status_code == 200
    assert "dev token" not in resp.json()["message"]
    assert not called


def test_email_service_noop_without_smtp_host(monkeypatch):
    from app.services import email as email_module
    from app.core.config import get_settings

    monkeypatch.setenv("SMTP_HOST", "")
    get_settings.cache_clear()
    try:
        assert email_module.send_email("x@example.com", "subj", "body") is False
    finally:
        get_settings.cache_clear()


def test_email_service_sends_via_smtp(monkeypatch):
    from app.services import email as email_module
    from app.core.config import get_settings

    class _FakeSMTP:
        def __init__(self, host, port, timeout=None):
            self.messages: list[str] = []

        def ehlo(self):
            pass

        def starttls(self):
            pass

        def login(self, user, password):
            pass

        def sendmail(self, from_addr, to_addrs, payload):
            self.messages.append(payload)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    captured: dict = {}

    def _factory(host, port, timeout=None):
        captured["server"] = _FakeSMTP(host, port, timeout)
        return captured["server"]

    monkeypatch.setenv("SMTP_HOST", "smtp.test.local")
    monkeypatch.setenv("SMTP_USERNAME", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    get_settings.cache_clear()
    monkeypatch.setattr(email_module.smtplib, "SMTP", _factory)
    try:
        assert email_module.send_email("to@example.com", "Subject", "Body") is True
        payload = captured["server"].messages[0]
        assert "Subject: Subject" in payload
        assert "to@example.com" in payload
    finally:
        get_settings.cache_clear()


def test_password_reset_confirm_flow_roundtrip(client, db):
    from app.core.security import create_password_reset_token

    email = "confirmme@example.com"
    old_password = "OldSecurePass123"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": old_password, "full_name": "Confirm"},
    )

    token = create_password_reset_token(email)
    bad = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": "not-a-real-token", "new_password": "NewSecurePass123"},
    )
    assert bad.status_code == 400

    ok = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "NewSecurePass123"},
    )
    assert ok.status_code == 200

    # Old password no longer works, new one does.
    assert (
        client.post("/api/v1/auth/login", json={"email": email, "password": old_password}).status_code == 401
    )
    assert (
        client.post("/api/v1/auth/login", json={"email": email, "password": "NewSecurePass123"}).status_code == 200
    )
