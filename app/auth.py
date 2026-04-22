"""
Autenticación JWT para el Widget de Chat
=========================================

Este módulo valida tokens JWT emitidos por el servidor externo (ej. un plugin de
Moodle) usando una clave secreta compartida (HS256). Expone una dependencia
``get_current_user`` que los endpoints de FastAPI usan para obtener de forma
segura el ``user_id`` y ``course_id`` del usuario autenticado.

Claims esperados en el payload del token:
    - ``sub``:        identificador del usuario (obligatorio)
    - ``course_id``:  identificador del curso (obligatorio)
    - ``exp``:        timestamp de expiración (obligatorio)
    - ``iss``:        emisor (opcional, se valida si JWT_ISSUER está definido)
    - ``iat``:        timestamp de emisión (opcional)
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"

# HTTPBearer extrae la cabecera "Authorization: Bearer <token>".
# auto_error=False para devolver 401 con nuestro mensaje en lugar de 403.
_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    """Usuario autenticado extraído del JWT validado."""

    user_id: str
    course_id: str
    raw_payload: dict


def _get_jwt_secret() -> str:
    """Obtiene la clave secreta del entorno, lanzando 500 si no está configurada."""
    secret = os.getenv("JWT_SECRET")
    if not secret:
        logger.error("❌ JWT_SECRET no está configurada en el entorno.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication is not configured.",
        )
    return secret


def verify_jwt_token(token: str) -> dict:
    """Valida firma, expiración y (opcionalmente) emisor del token.

    Retorna el payload decodificado. Lanza ``HTTPException(401)`` si el token
    es inválido, ha expirado o le faltan claims obligatorios.
    """
    secret = _get_jwt_secret()
    issuer = os.getenv("JWT_ISSUER")  # opcional

    try:
        decode_kwargs = {
            "key": secret,
            "algorithms": [JWT_ALGORITHM],
            "options": {"require": ["exp", "sub"]},
        }
        if issuer:
            decode_kwargs["issuer"] = issuer

        payload = jwt.decode(token, **decode_kwargs)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidIssuerError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT inválido: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not payload.get("course_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing required claim: course_id.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    """Dependencia de FastAPI que devuelve el usuario autenticado."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_jwt_token(credentials.credentials)

    return AuthenticatedUser(
        user_id=str(payload["sub"]),
        course_id=str(payload["course_id"]),
        raw_payload=payload,
    )
