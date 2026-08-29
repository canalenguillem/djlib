from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminUser, DbSession
from app.core.time import utcnow
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services import user_service
from app.services.user_service import PasswordPolicyError

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(admin: AdminUser, db: DbSession) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in user_service.list_users(db)]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, admin: AdminUser, db: DbSession) -> UserOut:
    if user_service.get_by_username(db, payload.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ese usuario ya existe."
        )
    if payload.email and user_service.get_by_email(db, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ese email ya esta en uso."
        )
    try:
        user = user_service.create_user(
            db,
            username=payload.username,
            password=payload.password,
            email=payload.email,
            role=payload.role,
        )
        db.commit()
    except PasswordPolicyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese nombre o email.",
        ) from exc
    db.refresh(user)
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, payload: UserUpdate, admin: AdminUser, db: DbSession
) -> UserOut:
    user = user_service.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado."
        )

    # Salvaguarda: un admin no puede dejarse a si mismo fuera del panel.
    if user.id == admin.id:
        if payload.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes desactivar tu propia cuenta.",
            )
        if payload.role is not None and payload.role != user.role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes cambiar tu propio rol.",
            )

    if payload.is_active is not None:
        user.is_active = payload.is_active
        if not payload.is_active:
            # Desactivar cierra las sesiones abiertas de ese usuario.
            user_service.revoke_all_refresh_tokens(db, user)
    if payload.role is not None:
        user.role = payload.role

    user.updated_at = utcnow()
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
