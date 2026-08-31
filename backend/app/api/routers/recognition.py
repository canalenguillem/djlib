import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.schemas.recognition import (
    DetectedSong,
    RecognitionResult,
    RecognitionStatus,
    ScreenshotResult,
)
from app.schemas.track import SearchCandidate
from app.services import downloader, recognition, screenshot, track_service
from app.services.downloader import DownloadError
from app.services.recognition import RecognitionError, RecognitionNotConfigured
from app.services.screenshot import ScreenshotError, ScreenshotNotConfigured

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recognize", tags=["recognition"])


@router.get("/status", response_model=RecognitionStatus)
def recognition_status(current_user: CurrentUser) -> RecognitionStatus:
    habilitado = recognition.is_enabled()
    return RecognitionStatus(
        enabled=habilitado,
        provider=recognition.provider_name() if habilitado else None,
        screenshot_enabled=screenshot.is_enabled(),
    )


@router.post("", response_model=RecognitionResult)
def recognize_audio(
    current_user: CurrentUser,
    db: DbSession,
    audio: UploadFile = File(..., description="Fragmento de 10-15 segundos"),
) -> RecognitionResult:
    """Identifica la cancion de un fragmento grabado con el microfono.

    Si la reconoce, devuelve tambien los candidatos de YouTube para que en el
    movil se pueda elegir y descargar sin otra vuelta al servidor.
    """
    if not recognition.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El reconocimiento de audio no esta configurado en el servidor.",
        )

    contenido = audio.file.read(settings.recognition_max_upload_bytes + 1)
    if len(contenido) > settings.recognition_max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El fragmento de audio es demasiado grande.",
        )
    if not contenido:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ha llegado audio. Vuelve a intentar la grabacion.",
        )

    try:
        encontrada = recognition.recognize(contenido, audio.filename or "fragmento.webm")
    except RecognitionNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except RecognitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    if encontrada is None:
        return RecognitionResult(recognized=False)

    # Buscar en YouTube es un extra: si falla, la identificacion sigue valiendo
    # y el usuario puede buscarla a mano.
    candidatos: list[SearchCandidate] = []
    try:
        resultados = downloader.search(encontrada.title, encontrada.artist)
        ya_estan = track_service.existing_video_ids(db, [r.video_id for r in resultados])
        limite = settings.max_song_duration_seconds
        candidatos = [
            SearchCandidate(
                video_id=r.video_id,
                title=r.title,
                channel=r.channel,
                duration_seconds=r.duration_seconds,
                url=r.url,
                thumbnail_url=r.thumbnail_url,
                already_in_library=r.video_id in ya_estan,
                too_long=bool(r.duration_seconds and r.duration_seconds > limite),
            )
            for r in resultados
        ]
    except DownloadError:
        logger.warning("Cancion reconocida pero la busqueda en YouTube ha fallado")

    return RecognitionResult(
        recognized=True,
        artist=encontrada.artist,
        title=encontrada.title,
        album=encontrada.album,
        release_date=encontrada.release_date,
        song_link=encontrada.song_link,
        candidates=candidatos,
    )


# Formatos que admite la API de vision de OpenAI.
IMAGENES_ADMITIDAS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


@router.post("/screenshot", response_model=ScreenshotResult)
def recognize_screenshot(
    current_user: CurrentUser,
    image: UploadFile = File(..., description="Captura con canciones visibles"),
) -> ScreenshotResult:
    """Lee las canciones que aparecen en una captura de pantalla.

    Pensado para la lista de Shazam: si lo dejas identificando solo durante la
    noche, al dia siguiente subes la captura y salen todas de una vez, en vez
    de teclearlas una por una.
    """
    if not screenshot.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La lectura de capturas no esta configurada en el servidor.",
        )

    tipo = (image.content_type or "").split(";")[0].strip().lower()
    if tipo not in IMAGENES_ADMITIDAS:
        admitidos = ", ".join(sorted(e.lstrip(".") for e in IMAGENES_ADMITIDAS.values()))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de imagen no admitido. Se aceptan: {admitidos}.",
        )

    contenido = image.file.read(settings.screenshot_max_bytes + 1)
    if len(contenido) > settings.screenshot_max_bytes:
        limite = settings.screenshot_max_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"La imagen supera el limite de {limite} MB.",
        )
    if not contenido:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="La imagen esta vacia."
        )

    try:
        canciones = screenshot.extract_songs(contenido, tipo)
    except ScreenshotNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except ScreenshotError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    return ScreenshotResult(
        songs=[DetectedSong(title=c.title, artist=c.artist) for c in canciones]
    )
