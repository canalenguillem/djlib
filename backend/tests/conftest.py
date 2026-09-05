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
from app.services import bpm as bpm_service
from app.services import spotify as spotify_service
from app.services import downloader, enrichment, preview as preview_service
from app.services import recognition, screenshot, user_service

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
        self.channel_queries: list[str] = []
        self.extension = "m4a"
        # El canal del que subio el video: la unica documentacion que hay de
        # quien monta un edit o un mashup.
        self.channel = downloader.ChannelInfo(
            name="DJ Nardini",
            url="https://www.youtube.com/@djnardini",
            avatar_url="https://yt3.googleusercontent.com/avatar.jpg",
            description="Edits y transiciones para pista.",
            follower_count=1920,
        )
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

    def channel_info(self, video_url: str):
        self.channel_queries.append(video_url)
        if self.error is not None:
            raise self.error
        return self.channel

    def search(self, title: str, artist: str | None):
        self.searched.append((title, artist))
        if self.error is not None:
            raise self.error
        return self.results

    def download(self, query: str, destination_dir: Path, video_id: str) -> Path:
        self.downloaded_queries.append(query)
        destination_dir.mkdir(parents=True, exist_ok=True)
        # Igual que yt-dlp: la extension la decide el flujo, no nosotros
        path = destination_dir / f"{video_id}.{self.extension}"
        path.write_bytes(b"\x00\x00\x00\x20ftypM4A audio-de-mentira")
        return path


@pytest.fixture
def fake_downloader(music_dir, monkeypatch) -> FakeDownloader:
    fake = FakeDownloader(music_dir)
    monkeypatch.setattr(downloader, "resolve", fake.resolve)
    monkeypatch.setattr(downloader, "download", fake.download)
    monkeypatch.setattr(downloader, "search", fake.search)
    monkeypatch.setattr(downloader, "channel_info", fake.channel_info)
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
                image_url="https://upload.wikimedia.org/blur.jpg",
                links={
                    "bandcamp": "https://blur.bandcamp.com/",
                    "official homepage": "https://blur.co.uk/",
                },
                genres=["britpop", "alternative rock", "indie rock", "art rock"],
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


class FakeRecognition:
    """Sustituye a AudD. Los tests deciden si reconoce, no reconoce o falla."""

    def __init__(self) -> None:
        self.track: recognition.RecognizedTrack | None = recognition.RecognizedTrack(
            artist="Blur",
            title="Song 2",
            album="Blur",
            release_date="1997-04-07",
            song_link="https://lis.tn/ejemplo",
        )
        self.error: Exception | None = None
        self.recibido: list[int] = []  # tamano de cada fragmento recibido

    def recognize(self, audio: bytes, filename: str = "fragmento.webm"):
        self.recibido.append(len(audio))
        if self.error is not None:
            raise self.error
        return self.track


@pytest.fixture
def fake_recognition(monkeypatch) -> FakeRecognition:
    fake = FakeRecognition()
    monkeypatch.setattr(recognition, "recognize", fake.recognize)
    monkeypatch.setattr(settings, "recognition_provider", "audd")
    monkeypatch.setattr(settings, "recognition_api_key", "clave-de-prueba")
    return fake


class FakeScreenshot:
    """Sustituye al modelo de vision de OpenAI."""

    def __init__(self) -> None:
        self.songs = [
            screenshot.DetectedSong(title="Song 2", artist="Blur"),
            screenshot.DetectedSong(title="Parklife", artist="Blur"),
            screenshot.DetectedSong(title="Sin artista", artist=None),
        ]
        self.error: Exception | None = None
        self.recibido: list[tuple[int, str]] = []  # (tamano, tipo mime)

    def extract_songs(self, image: bytes, mime_type: str = "image/png"):
        self.recibido.append((len(image), mime_type))
        if self.error is not None:
            raise self.error
        return self.songs


@pytest.fixture
def fake_screenshot(monkeypatch) -> FakeScreenshot:
    fake = FakeScreenshot()
    monkeypatch.setattr(screenshot, "extract_songs", fake.extract_songs)
    monkeypatch.setattr(settings, "openai_api_key", "clave-de-prueba")
    return fake


class FakeBpm:
    """Sustituye al detector de tempo, que llama a ffmpeg y a soundstretch."""

    def __init__(self) -> None:
        self.valor: int | None = 128
        self.analizados: list[str] = []

    def analyze(self, path):
        self.analizados.append(str(path))
        return self.valor


@pytest.fixture(autouse=True)
def fake_bpm(monkeypatch) -> FakeBpm:
    """autouse: descargar una cancion dispara el analisis, y sin esto cada test
    de la biblioteca lanzaria ffmpeg y soundstretch de verdad."""
    fake = FakeBpm()
    monkeypatch.setattr(bpm_service, "analyze", fake.analyze)
    return fake


class FakeSpotify:
    """Sustituye a Spotify: ni red ni credenciales."""

    def __init__(self) -> None:
        self.genres: dict[str, list[str]] = {"Rels B": ["urbano latino", "trap latino"]}
        self.played = [
            spotify_service.PlayedTrack(
                title="Song 2", artist="Blur", album="Blur",
                played_at="2026-08-31T22:10:00Z",
                spotify_url="https://open.spotify.com/track/abc",
                image_url="https://i.scdn.co/image/abc",
            ),
            spotify_service.PlayedTrack(
                title="Parklife", artist="Blur", album="Parklife",
                played_at="2026-08-31T22:05:00Z", spotify_url=None, image_url=None,
            ),
        ]
        self.error: Exception | None = None
        self.consultados: list[str] = []

    def artist_genres(self, nombre: str) -> list[str]:
        self.consultados.append(nombre)
        if self.error is not None:
            raise self.error
        return self.genres.get(nombre, [])

    def recently_played(self, token, limit=None):
        if self.error is not None:
            raise self.error
        return self.played


@pytest.fixture
def fake_spotify(monkeypatch) -> FakeSpotify:
    fake = FakeSpotify()
    monkeypatch.setattr(spotify_service, "artist_genres", fake.artist_genres)
    monkeypatch.setattr(spotify_service, "recently_played", fake.recently_played)
    monkeypatch.setattr(settings, "spotify_client_id", "id-de-prueba")
    monkeypatch.setattr(settings, "spotify_client_secret", "secreto")
    monkeypatch.setattr(
        settings, "spotify_redirect_uri", "https://ejemplo/api/spotify/callback"
    )
    return fake


@pytest.fixture(autouse=True)
def spotify_apagado(monkeypatch, request):
    """Por defecto Spotify esta desconfigurado en los tests, para que el
    respaldo de generos no salga a la red sin querer."""
    if "fake_spotify" in request.fixturenames:
        return
    monkeypatch.setattr(settings, "spotify_client_id", "")
    monkeypatch.setattr(settings, "spotify_client_secret", "")


@pytest.fixture
def fake_preview(monkeypatch, tmp_path) -> dict:
    """El fragmento se prepara con yt-dlp: en los tests se sustituye por un
    fichero de mentira para no salir a la red.

    No es autouse a proposito: los tests que prueban la construccion del
    fragmento necesitan la funcion de verdad, y un doble autouse se la
    sustituiria sin que se notase, dejandolos verdes sin probar nada.
    """
    estado: dict = {"construidos": [], "error": None}

    def build(url: str):
        estado["construidos"].append(url)
        if estado["error"] is not None:
            raise estado["error"]
        ruta = tmp_path / "fragmento.m4a"
        ruta.write_bytes(b"\x00\x00\x00\x20ftypM4A fragmento-de-mentira")
        return ruta

    monkeypatch.setattr(preview_service, "build", build)
    return estado
