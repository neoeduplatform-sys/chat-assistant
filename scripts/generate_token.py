"""
Generador de Tokens JWT para Testing
=====================================

Genera un JWT firmado con el mismo secreto que el backend (``JWT_SECRET``),
útil para probar los endpoints protegidos desde Postman o curl sin necesidad
de un plugin de Moodle.

Uso:
    # Con variables por defecto (lee JWT_SECRET de .env o el entorno)
    python scripts/generate_token.py

    # Personalizando claims
    python scripts/generate_token.py \
        --user-id user_test_123 \
        --course-id mantenimiento-mecanico \
        --hours 24

Luego, en Postman:
    Authorization → Type: Bearer Token → pega el token impreso.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

import jwt
from dotenv import load_dotenv


def build_payload(user_id: str, course_id: str, hours: int, issuer: str | None) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": user_id,
        "course_id": course_id,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(hours=hours)).timestamp()),
    }
    if issuer:
        payload["iss"] = issuer
    return payload


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Genera un JWT de prueba.")
    parser.add_argument("--user-id", default="user_test_123", help="Claim sub")
    parser.add_argument(
        "--course-id",
        default=os.getenv("DEFAULT_TEST_COURSE_ID", "default"),
        help="Claim course_id",
    )
    parser.add_argument(
        "--hours", type=int, default=24, help="Validez del token en horas"
    )
    parser.add_argument(
        "--issuer",
        default=os.getenv("JWT_ISSUER"),
        help="Claim iss (solo necesario si el backend tiene JWT_ISSUER)",
    )
    parser.add_argument(
        "--secret",
        default=os.getenv("JWT_SECRET"),
        help="Clave secreta; por defecto se lee de JWT_SECRET",
    )
    args = parser.parse_args()

    if not args.secret:
        print(
            "❌ JWT_SECRET no está configurada. Define la variable en .env o "
            "pásala con --secret.",
            file=sys.stderr,
        )
        return 1

    payload = build_payload(args.user_id, args.course_id, args.hours, args.issuer)
    token = jwt.encode(payload, args.secret, algorithm="HS256")

    print("✅ Token generado:\n")
    print(token)
    print("\nPayload:")
    for key, value in payload.items():
        print(f"  {key}: {value}")
    print("\nEn Postman: Authorization → Bearer Token → pega el token.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
