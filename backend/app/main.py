import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    artists,
    auth,
    batches,
    beatport,
    charts,
    crates,
    listens,
    recognition,
    spotify,
    tags,
    tracks,
    users,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not settings.startup_tasks_enabled:
        yield
        return

    # Las descargas sueltas viven dentro del proceso: un reinicio las deja
    # huerfanas. Al arrancar se marcan como error para que se vean y se puedan
    # reintentar. Las de las tandas, en cambio, se retoman solas.
    from app.db.session import SessionLocal
    from app.services import batch_service, track_service

    with SessionLocal() as db:
        recovered = track_service.recover_interrupted(db)
        retomadas = batch_service.recover(db)
    if recovered:
        logger.warning("%s descargas interrumpidas marcadas como error", recovered)
    if retomadas:
        logger.warning("%s canciones de tandas devueltas a la cola", retomadas)

    batch_service.start_workers(SessionLocal, settings.batch_workers)
    yield
    batch_service.stop_workers()


app = FastAPI(
    title="DJ Library API",
    version="0.6.0",
    description="Autenticacion, usuarios, biblioteca, artistas, reconocimiento y crates.",
    root_path=settings.api_root_path,
    lifespan=lifespan,
)

# Con el proxy del frontend, navegador y API comparten origen y CORS sobra.
# Solo se activa si CORS_ORIGINS trae algun origen (p. ej. si algun dia el
# frontend se sirve desde un dominio distinto al de la API).
if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tracks.router)
app.include_router(crates.router)
app.include_router(artists.router)
app.include_router(recognition.router)
app.include_router(spotify.router)
app.include_router(tags.router)
app.include_router(batches.router)
app.include_router(listens.router)
app.include_router(beatport.router)
app.include_router(charts.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
