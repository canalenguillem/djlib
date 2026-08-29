from collections.abc import Generator
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import app.core.security as security
import app.models  # noqa: F401  (registra los modelos en Base.metadata)
from app.api.deps import get_session_factory
from app.core.config import settings
from app.core.rate_limit import login_rate_limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app
from app.models.user import User, UserRole
from app.services import downloader, enrichment, user_service

# Los tests corren contra una base MariaDB aparte ("<db>_test"), creada por el
# script de init del contenedor de MariaDB. Asi se prueba el mismo motor que
# usa produccion (ENUM, colaciones, unicidad) y no un SQLite parecido.
engine = create_engine(settings.test_database_url, pool_pre_ping=True, future=True)
TestingSessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)

# argon2 esta calibrado para ser lento a proposito, lo que multiplica por
# quince la duracion de la suite. En tests basta con que la funcion sea la
# misma: se rebajan los parametros de coste.
security._hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)

ADMIN_PASSWORD = "AdminPass1234"
USER_PASSWORD = "UserPass1234"


@pytest.fixture(scope="session", autouse=True)
def database_schema() -> Generator[None, None, None]:
    """El esquema se crea una sola vez por sesion. Recrear las tablas en cada
    test es DDL, que en InnoDB es lento y ademas se dispara si la maquina tiene
    otras bases de datos trabajando al mismo tiempo."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def fresh_database(database_schema) -> Generator[None, None, None]:
    """Cada test arranca con las tablas vacias. Vaciar filas es mucho mas
    barato que rehacer el esquema."""
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    login_rate_limiter.clear()
    yield
    login_rate_limiter.clear()


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    # Las descargas en segundo plano deben escribir en la base de tests, no en
    # la real: se les inyecta la misma fabrica de sesiones.
    fastapi_app.dependency_overrides[get_session_factory] = lambda: TestingSessionLocal
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


def _make_user(**kwargs) -> User:
    session = TestingSessionLocal()
    try:
        user = user_service.create_user(session, **kwargs)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user
    finally:
        session.close()


@pytest.fixture
def admin_user() -> User:
    return _make_user(
        username="enguillem",
        password=ADMIN_PASSWORD,
        email="admin@example.com",
        role=UserRole.admin,
    )


@pytest.fixture
def normal_user() -> User:
    return _make_user(username="dj_pepe", password=USER_PASSWORD, role=UserRole.user)


def login(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def music_dir(tmp_path, monkeypatch) -> Path:
    """Aisla los mp3 de cada test en su propio directorio temporal."""
    destino = tmp_path / "music"
    destino.mkdir()
    monkeypatch.setattr(settings, "music_dir", str(destino))
    return destino


class FakeDownloader:
    """Sustituye a yt-dlp: ni red ni subprocesos, pero el mismo contrato.

    Los tests configuran que debe devolver `resolve` (o que error lanzar) y
    `download` escribe un fichero de mentira en el directorio de musica.
    """

    def __init__(self, destination: Path) -> None:
        self.destination = destination
        self.info = downloader.MediaInfo(
            video_id="dQw4w9WgXcQ",
            title="Song 2",
            artist="Blur",
            duration_seconds=121,
            webpage_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            site="youtube",
        )
        self.error: Exception | None = None
        self.resolved_queries: list[str] = []
        self.downloaded_queries: list[str] = []
        self.searched: list[tuple[str, str | None]] = []
        # Lo que devuelve una busqueda: un mix largo primero, como hace YouTube
        self.results = [
            downloader.SearchResult(
                video_id="mixlargo123",
                title="Puro Perreo Vol.37 Mix (Bad Bunny, Karol G, etc)",
                channel="DJ Nayef Qva",
                duration_seconds=2527,
                url="https://www.youtube.com/watch?v=mixlargo123",
                thumbnail_url="https://i.ytimg.com/vi/mixlargo123/hqdefault.jpg",
            ),
            downloader.SearchResult(
                video_id="dQw4w9WgXcQ",
                title="Blur - Song 2 (Official Music Video)",
                channel="Blur",
                duration_seconds=121,
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                thumbnail_url="https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
            ),
        ]

    def resolve(self, query: str):
        self.resolved_queries.append(query)
        if self.error is not None:
            raise self.error
        return self.info

    def search(self, title: str, artist: str | None):
        self.searched.append((title, artist))
        if self.error is not None:
            raise self.error
        return self.results

    def download(self, query: str, destination_dir: Path, video_id: str) -> Path:
        self.downloaded_queries.append(query)
        destination_dir.mkdir(parents=True, exist_ok=True)
        path = destination_dir / f"{video_id}.mp3"
        path.write_bytes(b"ID3fake-mp3-para-tests")
        return path


@pytest.fixture
def fake_downloader(music_dir, monkeypatch) -> FakeDownloader:
    fake = FakeDownloader(music_dir)
    monkeypatch.setattr(downloader, "resolve", fake.resolve)
    monkeypatch.setattr(downloader, "download", fake.download)
    monkeypatch.setattr(downloader, "search", fake.search)
    return fake


class FakeEnrichment:
    """Sustituye a MusicBrainz + Wikipedia: mismo contrato, sin red."""

    def __init__(self) -> None:
        self.facts: dict[str, enrichment.ArtistFacts] = {
            "Blur": enrichment.ArtistFacts(
                name="Blur",
                musicbrainz_id="ba853904-ae25-4ebb-89d6-c44cfbd71bd2",
                country="GB",
                begin_year=1988,
                artist_type="Group",
                bio="Blur es un grupo britanico de rock formado en Londres en 1988.",
                wikipedia_url="https://es.wikipedia.org/wiki/Blur",
                relations=[
                    enrichment.RelationFact("Damon Albarn", "miembros"),
                    enrichment.RelationFact("Gorillaz", "colaboracion"),
                ],
            ),
            "Robbie Williams": enrichment.ArtistFacts(
                name="Robbie Williams",
                country="GB",
                begin_year=1974,
                artist_type="Person",
                bio="Cantante britanico.",
                relations=[enrichment.RelationFact("Take That", "miembro de")],
            ),
            "Take That": enrichment.ArtistFacts(
                name="Take That",
                country="GB",
                begin_year=1990,
                artist_type="Group",
                bio="Boy band britanica.",
                # MusicBrainz devuelve la relacion por los dos lados
                relations=[enrichment.RelationFact("Robbie Williams", "miembros")],
            ),
        }
        self.error: Exception | None = None
        self.lookups: list[str] = []

    def lookup(self, name: str):
        self.lookups.append(name)
        if self.error is not None:
            raise self.error
        return self.facts.get(name)


@pytest.fixture(autouse=True)
def fake_enrichment(monkeypatch) -> FakeEnrichment:
    """autouse a proposito: descargar una cancion crea la ficha de su artista y
    consulta las fuentes externas. Sin esto, cualquier test de la biblioteca
    saldria a internet de verdad, y la suite pasaria de segundos a minutos
    ademas de depender de que MusicBrainz este de buen humor.
    """
    fake = FakeEnrichment()
    monkeypatch.setattr(enrichment, "lookup", fake.lookup)
    return fake
