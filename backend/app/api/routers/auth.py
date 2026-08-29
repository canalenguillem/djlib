from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import client_ip, login_rate_limiter
from app.core.security import create_access_token, verify_password
from app.core.time import utcnow
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
from app.schemas.user import EmailUpdate, PasswordChange, UserOut
from app.services import user_service
from app.services.user_service import PasswordPolicyError

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Usuario o contrasena incorrectos.",
)


def _issue_pair(db, user) -> TokenPair:
    access_token, expires_in = create_access_token(user.id, user.role.value)
    refresh_token = user_service.issue_refresh_token(db, user)
    return TokenPair(
        access_token=access_token, refresh_token=refresh_token, expires_in=expires_in
    )


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenPair:
    ip = client_ip(request)
    retry_after = login_rate_limiter.retry_after(ip)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Prueba de nuevo mas tarde.",
            headers={"Retry-After": str(retry_after)},
        )

    user = user_service.authenticate(db, payload.username, payload.password)
    if user is None:
        login_rate_limiter.register_failure(ip)
        raise INVALID_CREDENTIALS

    login_rate_limiter.reset(ip)
    user.last_login_at = utcnow()
    tokens = _issue_pair(db, user)
    db.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    token = user_service.get_refresh_token(db, payload.refresh_token)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token no valido."
        )

    if not token.is_usable():
        # Reutilizar un token ya rotado o revocado huele a robo de credenciales:
        # cerramos todas las sesiones del usuario por precaucion.
        user_service.revoke_all_refresh_tokens(db, token.user)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion expirada. Vuelve a iniciar sesion.",
        )

    user = token.user
    if not user.is_active:
        user_service.revoke_all_refresh_tokens(db, user)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario desactivado."
        )

    user_service.revoke_refresh_token(token)
    tokens = _issue_pair(db, user)
    db.commit()
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, db: DbSession) -> Response:
    token = user_service.get_refresh_token(db, payload.refresh_token)
    if token is not None:
        user_service.revoke_refresh_token(token)
        db.commit()
    # Siempre 204: cerrar sesion nunca debe fallar en el cliente.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def read_me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)


@router.patch("/me/password", response_model=TokenPair)
def change_my_password(
    payload: PasswordChange, current_user: CurrentUser, db: DbSession
) -> TokenPair:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contrasena actual no es correcta.",
        )
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contrasena debe ser distinta de la actual.",
        )
    try:
        user_service.change_password(db, current_user, payload.new_password)
    except PasswordPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    # El cambio revoca las sesiones anteriores; devolvemos un par nuevo para
    # que la sesion actual siga viva sin obligar a volver a hacer login.
    tokens = _issue_pair(db, current_user)
    db.commit()
    return tokens


@router.patch("/me/email", response_model=UserOut)
def update_my_email(
    payload: EmailUpdate, current_user: CurrentUser, db: DbSession
) -> UserOut:
    current_user.email = payload.email or None
    current_user.updated_at = utcnow()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese email ya esta en uso por otro usuario.",
        ) from exc
    db.refresh(current_user)
    return UserOut.model_validate(current_user)
