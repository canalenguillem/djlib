from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth, users
from app.core.config import settings

app = FastAPI(
    title="DJ Library API",
    version="0.1.0",
    description="Modulo de autenticacion y gestion de usuarios.",
    root_path=settings.api_root_path,
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


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
