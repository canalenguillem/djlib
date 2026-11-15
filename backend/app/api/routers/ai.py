"""Las claves de IA de cada usuario: las pone, las prueba y elige cual usar."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.ai import AiKeyIn, AiProviderOut, AiSelect, AiSettings, AiTestResult
from app.services import ai_keys
from app.services.ai_keys import AiKeyError

router = APIRouter(prefix="/me/ai", tags=["ai"])


def _ajustes(db, user) -> AiSettings:
    guardadas = ai_keys.claves(db, user)
    return AiSettings(
        selected=user.ai_provider,
        providers=[
            AiProviderOut(
                id=p.id,
                name=p.nombre,
                default_model=p.modelo,
                console_url=p.consola,
                configured=p.id in guardadas,
                key_hint=guardadas[p.id].pista if p.id in guardadas else None,
                model=guardadas[p.id].model if p.id in guardadas else None,
            )
            for p in ai_keys.PROVEEDORES.values()
        ],
    )


def _400(exc: AiKeyError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("", response_model=AiSettings)
def ver(current_user: CurrentUser, db: DbSession) -> AiSettings:
    return _ajustes(db, current_user)


@router.put("/selected", response_model=AiSettings)
def elegir(payload: AiSelect, current_user: CurrentUser, db: DbSession) -> AiSettings:
    try:
        ai_keys.elegir(db, current_user, payload.provider)
    except AiKeyError as exc:
        raise _400(exc) from exc
    db.commit()
    return _ajustes(db, current_user)


@router.put("/{provider}", response_model=AiSettings)
def guardar(provider: str, payload: AiKeyIn, current_user: CurrentUser, db: DbSession) -> AiSettings:
    try:
        ai_keys.guardar(db, current_user, provider, payload.api_key, payload.model)
    except AiKeyError as exc:
        raise _400(exc) from exc
    db.commit()
    return _ajustes(db, current_user)


@router.delete("/{provider}", response_model=AiSettings)
def borrar(provider: str, current_user: CurrentUser, db: DbSession) -> AiSettings:
    try:
        ai_keys.borrar(db, current_user, provider)
    except AiKeyError as exc:
        raise _400(exc) from exc
    db.commit()
    return _ajustes(db, current_user)


@router.post("/{provider}/test", response_model=AiTestResult)
def probar(provider: str, current_user: CurrentUser, db: DbSession) -> AiTestResult:
    """Comprueba la clave guardada sin gastar: pide la ficha del modelo."""
    try:
        conf = ai_keys.config(db, current_user, provider)
        if conf is None:
            raise AiKeyError("No hay clave guardada para ese proveedor.")
        return AiTestResult(ok=True, message=ai_keys.probar(conf))
    except AiKeyError as exc:
        return AiTestResult(ok=False, message=str(exc))
