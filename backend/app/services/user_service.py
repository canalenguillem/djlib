"""Reglas de negocio de usuarios y sesiones.

Los routers se limitan a HTTP; aqui vive la logica para que sea reutilizable
(seed, tests, futuros modulos) y facil de probar.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.core.time import utcnow
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole


class PasswordPolicyError(ValueError):
    pass


def validate_password(password: str) -> None:
    if len(password) < settings.min_password_length:
        raise PasswordPolicyError(
            f"La contrasena debe tener al menos {settings.min_password_length} caracteres."
        )
    if password.strip() != password:
        raise PasswordPolicyError(
            "La contrasena no puede empezar ni terminar con espacios."
        )


def get_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)))


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    email: str | None = None,
    role: UserRole = UserRole.user,
    is_active: bool = True,
) -> User:
    validate_password(password)
    now = utcnow()
    user = User(
        username=username,
        email=email or None,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
        password_changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()
    return user


def authenticate(db: Session, username: str, password: str) -> User | None:
    """Devuelve el usuario si las credenciales son validas y esta activo.

    Siempre se verifica un hash (aunque el usuario no exista) para que el
    tiempo de respuesta no revele que usernames estan dados de alta.
    """
    user = get_by_username(db, username)
    candidate_hash = user.password_hash if user else _DUMMY_HASH
    password_ok = verify_password(password, candidate_hash)
    if user is None or not password_ok or not user.is_active:
        return None
    return user


def change_password(db: Session, user: User, new_password: str) -> None:
    validate_password(new_password)
    now = utcnow()
    user.password_hash = hash_password(new_password)
    user.password_changed_at = now
    user.updated_at = now
    revoke_all_refresh_tokens(db, user)


# --- Refresh tokens ---------------------------------------------------------


def issue_refresh_token(db: Session, user: User) -> str:
    raw, token_hash = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    return raw


def get_refresh_token(db: Session, raw_token: str) -> RefreshToken | None:
    return db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )


def revoke_refresh_token(token: RefreshToken) -> None:
    if token.revoked_at is None:
        token.revoked_at = utcnow()


def revoke_all_refresh_tokens(db: Session, user: User) -> None:
    now = utcnow()
    tokens = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    )
    for token in tokens:
        token.revoked_at = now


_DUMMY_HASH = hash_password("contrasena-inexistente-para-igualar-tiempos")
