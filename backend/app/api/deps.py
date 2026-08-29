from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.core.time import to_epoch
from app.db.session import get_db
from app.models.user import User
from app.services import user_service

bearer_scheme = HTTPBearer(auto_error=False)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sesion no valida o expirada.",
    headers={"WWW-Authenticate": "Bearer"},
)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise CREDENTIALS_ERROR

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise CREDENTIALS_ERROR

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise CREDENTIALS_ERROR from None

    user = user_service.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise CREDENTIALS_ERROR

    # Un cambio de contrasena invalida los access tokens emitidos antes.
    issued_at = payload.get("iat")
    if issued_at is None or issued_at < int(to_epoch(user.password_changed_at)):
        raise CREDENTIALS_ERROR

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(current_user: CurrentUser) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador.",
        )
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
