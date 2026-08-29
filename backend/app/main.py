import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth, tags, tracks, users
from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Las descargas viven dentro del proceso: un reinicio las deja huerfanas.
    # Al arrancar se marcan como error para que se vean y se puedan reintentar.
    from app.db.session import SessionLocal
    from app.services import track_service

    with SessionLocal() as db:
        recovered = track_service.recover_interrupted(db)
    if recovered:
        logger.warning("%s descargas interrumpidas marcadas como error", recovered)
    yield


app = FastAPI(
    title="DJ Library API",
    version="0.2.0",
    description="Autenticacion, usuarios y biblioteca musical.",
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
app.include_router(tags.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
