"""Siembra el usuario admin inicial. Idempotente: si ya existe, no toca nada.

La contrasena se toma de SEED_ADMIN_PASSWORD; nunca esta en el codigo.
Uso:  python -m app.cli.seed
"""

import sys

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import UserRole
from app.services import user_service
from app.services.user_service import PasswordPolicyError


def main() -> int:
    username = settings.seed_admin_username
    password = settings.seed_admin_password

    if not password:
        print(
            "[seed] ERROR: SEED_ADMIN_PASSWORD no esta definida en el entorno (.env). "
            "No se crea ningun usuario.",
            file=sys.stderr,
        )
        return 1

    with SessionLocal() as db:
        existing = user_service.get_by_username(db, username)
        if existing is not None:
            print(f"[seed] El usuario '{username}' ya existe (id={existing.id}). Nada que hacer.")
            return 0

        try:
            user = user_service.create_user(
                db,
                username=username,
                password=password,
                email=settings.seed_admin_email or None,
                role=UserRole.admin,
            )
        except PasswordPolicyError as exc:
            print(f"[seed] ERROR: {exc}", file=sys.stderr)
            return 1

        db.commit()
        print(f"[seed] Usuario admin '{user.username}' creado (id={user.id}).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
