import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.schemas.recognition import RecognitionResult, RecognitionStatus
from app.schemas.track import SearchCandidate
from app.services import downloader, recognition, track_service
from app.services.downloader import DownloadError
from app.services.recognition import RecognitionError, RecognitionNotConfigured

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recognize", tags=["recognition"])


@router.get("/status", response_model=RecognitionStatus)
def recognition_status(current_user: CurrentUser) -> RecognitionStatus:
    habilitado = recognition.is_enabled()
    return RecognitionStatus(
        enabled=habilitado,
        provider=recognition.provider_name() if habilitado else None,
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
