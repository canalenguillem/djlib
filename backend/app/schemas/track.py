from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.models.track import TrackSource, TrackStatus
from app.schemas.artist import ArtistBrief
from app.schemas.tag import TagOut


class TrackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def thumbnail_url(self) -> str | None:
        """La caratula sale del id del video, asi que no hay nada que guardar.
        Los ficheros subidos por el usuario no tienen."""
        if self.source_site == "youtube" and self.source_video_id:
            return f"https://i.ytimg.com/vi/{self.source_video_id}/mqdefault.jpg"
        return None

    id: int
    title: str
    artist_text: str | None = None
    duration_seconds: int | None = None
    ingest_source: TrackSource
    request_query: str
    source_url: str | None = None
    source_site: str | None = None
    source_video_id: str | None = None
    status: TrackStatus
    error_message: str | None = None
    file_size: int | None = None
    bpm: int | None = None
    energy: int | None = None
    added_by_user_id: int | None = None
    downloaded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    tags: list[TagOut] = []
    artists: list[ArtistBrief] = []
    # Crates en los que esta, del primero en que entro al ultimo
    crate_ids: list[int] = []
    # Crate al que ira cuando termine de descargarse
    pending_crate_id: int | None = None


class TrackCrateMove(BaseModel):
    """Cambiar la cancion de crate: sale de `from_crate_id` (si se da) y entra
    en `crate_id` (si se da). Con los dos vacios no hace nada."""

    crate_id: int | None = None
    from_crate_id: int | None = None


class TrackExport(BaseModel):
    """Canciones sueltas para bajar en un zip; el tope es el de una pagina
    larga de la biblioteca."""

    track_ids: list[int] = Field(min_length=1, max_length=500)


class TrackPage(BaseModel):
    items: list[TrackOut]
    total: int
    limit: int
    offset: int


class TrackFromUrl(BaseModel):
    url: str = Field(min_length=5, max_length=500)
    # Crate al que ira cuando este descargada
    crate_id: int | None = None


class TrackFromSearch(BaseModel):
    """Basta con uno de los dos. Solo con el artista se piden sus temas mas
    relevantes, que es como se explora a alguien de quien no recuerdas titulos."""

    title: str | None = Field(default=None, max_length=300)
    artist: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def al_menos_uno(self) -> "TrackFromSearch":
        if not (self.title or "").strip() and not (self.artist or "").strip():
            raise ValueError("Indica un titulo, un artista, o los dos.")
        return self


class TrackUpdate(BaseModel):
    """Correccion manual de los metadatos y de la energia.

    `energy` va de 1 a 5 como las estrellas que usan los DJ: 1 para el warm-up,
    5 para el pico de la noche. No es una nota de calidad.
    """

    title: str | None = Field(default=None, min_length=1, max_length=300)
    artist_text: str | None = Field(default=None, max_length=300)
    energy: int | None = Field(default=None, ge=1, le=5)
    bpm: int | None = Field(default=None, ge=20, le=400)


class TrackTagsUpdate(BaseModel):
    tag_ids: list[int] = []


class SearchCandidate(BaseModel):
    """Un resultado de YouTube tal y como se le ofrece al usuario."""

    video_id: str
    title: str
    channel: str | None = None
    duration_seconds: int | None = None
    url: str
    thumbnail_url: str | None = None
    # Marcas para que se vea de un vistazo que conviene y que no
    already_in_library: bool = False
    too_long: bool = False
    # Si ya esta, la cancion de la biblioteca: para poder meterla en un crate
    # desde los propios resultados
    track_id: int | None = None
    crate_ids: list[int] = []
    pending_crate_id: int | None = None


class SearchResults(BaseModel):
    query: str
    candidates: list[SearchCandidate]


class WaveformOut(BaseModel):
    """Forma de onda en tres bandas, un valor de 0 a 255 por tramo."""

    bins: int
    low: list[int]
    mid: list[int]
    high: list[int]
