from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion de la aplicacion, leida del entorno (.env)."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Base de datos ---
    db_host: str = "db"
    db_port: int = 3306
    mariadb_database: str = "djlibrary"
    mariadb_user: str = "djlibrary"
    mariadb_password: str = ""

    # --- JWT ---
    # Sin valor por defecto a proposito: si falta, la app no arranca.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14

    # --- App ---
    cors_origins: str = ""
    # Prefijo con el que el proxy expone la API (para que /docs y /openapi.json
    # generen URLs correctas). Vacio si se accede al backend directamente.
    api_root_path: str = ""
    min_password_length: int = 10
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300
    trust_proxy_headers: bool = False

    # --- Biblioteca musical ---
    music_dir: str = "/data/music"
    # yt-dlp puede tardar bastante con conexiones lentas o videos largos.
    download_timeout_seconds: int = 900
    # Tope duro para una URL concreta: descarta directos y albumes enteros.
    max_track_duration_seconds: int = 3600
    # Tope al elegir entre los resultados de una busqueda. El primer resultado
    # de YouTube para una consulta vaga suele ser un mix de una hora, asi que
    # se descartan los que no tienen duracion de cancion.
    max_song_duration_seconds: int = 900
    # Cuantos resultados se miran antes de elegir.
    search_candidates: int = 5
    # Buscando solo por artista se explora, no se busca algo concreto: conviene
    # ver mas para hacerse una idea de lo que hay.
    search_artist_candidates: int = 10
    ytdlp_audio_quality: str = "0"  # 0 = mejor calidad VBR
    # Cookies exportadas del navegador, si YouTube empieza a pedir verificacion.
    ytdlp_cookies_file: str | None = None

    # --- Fichas de artista (MusicBrainz + Wikipedia) ---
    enrichment_enabled: bool = True
    musicbrainz_base_url: str = "https://musicbrainz.org/ws/2"
    # MusicBrainz exige un User-Agent identificable; sin el bloquea por IP.
    enrichment_user_agent: str = "DJLibrary/0.3 (self-hosted; https://github.com/canalenguillem/djlib)"
    enrichment_timeout_seconds: int = 15
    wikipedia_lang: str = "es"

    # --- Reconocimiento de audio ---
    recognition_provider: str = ""  # "audd" | vacio = desactivado
    recognition_api_key: str = ""
    recognition_timeout_seconds: int = 45
    # Un fragmento de 15 s en opus ronda los 100 KB; el tope deja margen de
    # sobra y corta subidas absurdas antes de gastar una peticion de AudD.
    recognition_max_upload_bytes: int = 10 * 1024 * 1024

    # --- Seed ---
    seed_admin_username: str = "enguillem"
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None

    def database_url(self, database: str | None = None) -> str:
        name = database or self.mariadb_database
        return (
            f"mysql+pymysql://{quote_plus(self.mariadb_user)}:"
            f"{quote_plus(self.mariadb_password)}@{self.db_host}:{self.db_port}/"
            f"{name}?charset=utf8mb4"
        )

    @property
    def test_database_url(self) -> str:
        return self.database_url(f"{self.mariadb_database}_test")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
