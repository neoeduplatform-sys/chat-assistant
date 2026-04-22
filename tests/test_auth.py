"""
Tests básicos para el módulo ``app.auth``.

Cubren el flujo mínimo descrito en el plan de implementación JWT:
  - Un token válido devuelve ``AuthenticatedUser`` con los claims correctos.
  - Un token inválido o expirado devuelve ``HTTPException(401)``.

Se prueban las funciones directamente (sin TestClient) para evitar
arrancar el lifespan de FastAPI, que requiere Supabase y Gemini.

Ejecución:
    pytest tests/test_auth.py -v
"""

from __future__ import annotations

import datetime as dt

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import AuthenticatedUser, get_current_user, verify_jwt_token


TEST_SECRET = "test-secret-do-not-use-in-production"


def _make_token(payload: dict, secret: str = TEST_SECRET) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def _base_payload(**overrides) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": "user_test_123",
        "course_id": "course_abc",
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(hours=2)).timestamp()),
    }
    payload.update(overrides)
    return payload


@pytest.fixture(autouse=True)
def _configure_jwt_env(monkeypatch):
    """Garantiza un secreto conocido y sin issuer por defecto en cada test."""
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.delenv("JWT_ISSUER", raising=False)


# ---------------------------------------------------------------------------
# verify_jwt_token
# ---------------------------------------------------------------------------


def test_verify_valid_token_returns_payload():
    token = _make_token(_base_payload())

    payload = verify_jwt_token(token)

    assert payload["sub"] == "user_test_123"
    assert payload["course_id"] == "course_abc"


def test_verify_expired_token_raises_401():
    expired = _base_payload(
        exp=int(
            (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)).timestamp()
        )
    )
    token = _make_token(expired)

    with pytest.raises(HTTPException) as excinfo:
        verify_jwt_token(token)

    assert excinfo.value.status_code == 401
    assert "expired" in excinfo.value.detail.lower()


def test_verify_token_with_bad_signature_raises_401():
    token = _make_token(_base_payload(), secret="another-secret")

    with pytest.raises(HTTPException) as excinfo:
        verify_jwt_token(token)

    assert excinfo.value.status_code == 401


def test_verify_token_missing_course_id_raises_401():
    payload = _base_payload()
    payload.pop("course_id")
    token = _make_token(payload)

    with pytest.raises(HTTPException) as excinfo:
        verify_jwt_token(token)

    assert excinfo.value.status_code == 401
    assert "course_id" in excinfo.value.detail


def test_verify_token_validates_issuer_when_configured(monkeypatch):
    monkeypatch.setenv("JWT_ISSUER", "moodle-prod")

    token_ok = _make_token(_base_payload(iss="moodle-prod"))
    payload = verify_jwt_token(token_ok)
    assert payload["iss"] == "moodle-prod"

    token_bad = _make_token(_base_payload(iss="otro-issuer"))
    with pytest.raises(HTTPException) as excinfo:
        verify_jwt_token(token_bad)
    assert excinfo.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user (dependencia FastAPI)
# ---------------------------------------------------------------------------


def test_get_current_user_with_valid_credentials():
    token = _make_token(_base_payload())
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    user = get_current_user(credentials=credentials)

    assert isinstance(user, AuthenticatedUser)
    assert user.user_id == "user_test_123"
    assert user.course_id == "course_abc"


def test_get_current_user_without_credentials_raises_401():
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(credentials=None)

    assert excinfo.value.status_code == 401


def test_get_current_user_with_invalid_token_raises_401():
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="not-a-valid-token"
    )

    with pytest.raises(HTTPException) as excinfo:
        get_current_user(credentials=credentials)

    assert excinfo.value.status_code == 401
