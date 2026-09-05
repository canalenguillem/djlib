import logging

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.text import normalize_key
from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.spotify import SpotifyAccount
from app.models.track import Track, TrackStatus
from app.schemas.spotify import (
    PlayedTrackOut,
    RecentlyPlayed,
    SpotifyAuthUrl,
    SpotifyStatus,
)
from app.services import spotify
from app.services.spotify import SpotifyError, SpotifyNotConfigured

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/spotify", tags=["spotify"])


def _cuenta(db, user_id: int) -> SpotifyAccount | None:
    return db.get(SpotifyAccount, user_id)


def _access_token(db, cuenta: SpotifyAccount) -> str:
    """Token valido, renovandolo si hace falta."""
    if cuenta.token_vigente():
        return cuenta.access_token  # type: ignore[return-value]

    tokens = spotify.refresh_tokens(cuenta.refresh_token)
    cuenta.access_token = tokens.access_token
    cuenta.refresh_token = tokens.refresh_token or cuenta.refresh_token
    cuenta.expires_at = spotify.expires_at(tokens.expires_in)
    cuenta.updated_at = utcnow()
    db.commit()
    return tokens.access_token


@router.get("/status", response_model=SpotifyStatus)
def spotify_status(current_user: CurrentUser, db: DbSession) -> SpotifyStatus:
    cuenta = _cuenta(db, current_user.id)

    # Si al conectar no se pudo leer el perfil (pasa si la cuenta aun no estaba
    # dada de alta en la app), se reintenta ahora. Ver que cuenta es de verdad
    # importa: es lo que delata haber autorizado la equivocada.
    if cuenta is not None and not cuenta.display_name:
        try:
            perfil = spotify._get("/me", _access_token(db, cuenta))
            cuenta.display_name = perfil.get("display_name") or perfil.get("id")
            cuenta.spotify_user_id = perfil.get("id")
            cuenta.updated_at = utcnow()
            db.commit()
        except SpotifyError as exc:
            logger.info("No se pudo leer el perfil de Spotify: %s", exc)

    return SpotifyStatus(
        enabled=spotify.is_enabled(),
        connected=cuenta is not None,
        display_name=cuenta.display_name if cuenta else None,
    )


@router.post("/authorize", response_model=SpotifyAuthUrl)
def spotify_authorize(current_user: CurrentUser) -> SpotifyAuthUrl:
    """Devuelve la URL a la que mandar al usuario para que de permiso."""
    try:
        estado = spotify.crear_estado(current_user.id)
        return SpotifyAuthUrl(url=spotify.authorize_url(estado))
    except SpotifyNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.get("/callback", include_in_schema=False)
def spotify_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    """Vuelta de Spotify tras autorizar.

    Aqui llega el navegador siguiendo una redireccion, sin cabecera de
    autenticacion: por eso el usuario se identifica con el `state`, que se creo
    al pedir la URL y solo sirve una vez.
    """
    destino = settings.spotify_return_url

    if error:
        return RedirectResponse(f"{destino}?error={error}")
    if not code or not state:
        return RedirectResponse(f"{destino}?error=respuesta_incompleta")

    user_id = spotify.consumir_estado(state)
    if user_id is None:
        return RedirectResponse(f"{destino}?error=estado_no_valido")

    try:
        tokens = spotify.exchange_code(code)
    except SpotifyError as exc:
        logger.warning("Fallo al canjear el codigo de Spotify: %s", exc)
        return RedirectResponse(f"{destino}?error=canje")

    perfil = {}
    try:
        perfil = spotify._get("/me", tokens.access_token)
    except SpotifyError:
        pass  # El nombre es un adorno; sin el se puede seguir

    with SessionLocal() as db:
        cuenta = db.get(SpotifyAccount, user_id)
        if cuenta is None:
            cuenta = SpotifyAccount(user_id=user_id, refresh_token=tokens.refresh_token or "")
            db.add(cuenta)
        if tokens.refresh_token:
            cuenta.refresh_token = tokens.refresh_token
        cuenta.access_token = tokens.access_token
        cuenta.expires_at = spotify.expires_at(tokens.expires_in)
        cuenta.scope = tokens.scope
        cuenta.spotify_user_id = perfil.get("id")
        cuenta.display_name = perfil.get("display_name") or perfil.get("id")
        cuenta.updated_at = utcnow()
        db.commit()

    return RedirectResponse(f"{destino}?connected=1")


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
def spotify_disconnect(current_user: CurrentUser, db: DbSession) -> Response:
    cuenta = _cuenta(db, current_user.id)
    if cuenta is not None:
        db.delete(cuenta)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/recently-played", response_model=RecentlyPlayed)
def spotify_recently_played(
    current_user: CurrentUser, db: DbSession, limit: int = Query(default=50, ge=1, le=50)
) -> RecentlyPlayed:
    """Lo ultimo que has escuchado, marcando lo que ya tienes."""
    if not spotify.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Spotify no esta configurado en el servidor.",
        )
    cuenta = _cuenta(db, current_user.id)
    if cuenta is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Todavia no has conectado tu cuenta de Spotify.",
        )

    try:
        token = _access_token(db, cuenta)
        canciones = spotify.recently_played(token, limit)
    except SpotifyError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    # Se comparan por la misma clave normalizada que usa la deduplicacion
    claves = {normalize_key(c.artist, c.title): c for c in canciones}
    existentes = set(
        db.scalars(
            Track.__table__.select()
            .with_only_columns(Track.normalized_key)
            .where(
                Track.normalized_key.in_(list(claves)),
                Track.status.in_(
                    (TrackStatus.ready, TrackStatus.pending, TrackStatus.downloading)
                ),
            )
        )
    )

    return RecentlyPlayed(
        items=[
            PlayedTrackOut(
                title=c.title,
                artist=c.artist,
                album=c.album,
                played_at=c.played_at,
                spotify_url=c.spotify_url,
                image_url=c.image_url,
                already_in_library=normalize_key(c.artist, c.title) in existentes,
            )
            for c in canciones
        ]
    )
