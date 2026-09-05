"""Fichas de artista: alta automatica al descargar, enriquecido y edicion."""

from __future__ import annotations

import logging
import re

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.text import slugify
from app.core.time import utcnow
from app.models.artist import Artist, ArtistRelation, EnrichmentStatus
from app.models.tag import Tag, TagKind
from app.models.track import Track, TrackStatus
from app.services import downloader, enrichment, spotify, tag_service
from app.services.enrichment import ArtistFacts, EnrichmentError

logger = logging.getLogger(__name__)

# Solo se parte por "feat.", que es inequivoco. NO se parte por "&" ni por ","
# a proposito: "Simon & Garfunkel" o "Earth, Wind & Fire" son un unico artista,
# y equivocarse ahi ensucia la biblioteca mas de lo que ayuda. Para el resto de
# colaboraciones, el usuario asigna los artistas a mano desde la ficha.
_FEATURING = re.compile(
    r"\s+(?:feat\.?|ft\.?|featuring|con la colaboraci[oó]n de|with)\s+", re.IGNORECASE
)


def split_artist_names(artist_text: str | None) -> list[str]:
    if not artist_text or not artist_text.strip():
        return []
    parts = [p.strip(" -–—,&") for p in _FEATURING.split(artist_text)]
    seen: set[str] = set()
    names: list[str] = []
    for part in parts:
        if not part:
            continue
        key = slugify(part)
        if not key or key in seen:
            continue
        seen.add(key)
        names.append(part)
    return names


# Siglas que .title() dejaria mal: "Edm", "Idm", "Dnb"...
SIGLAS = {"edm", "idm", "dnb", "ukg", "nrg", "r&b", "uk", "us", "hi-nrg", "adhd"}


def genre_label(genero: str) -> str:
    """"r&b" -> "R&B", "electro house" -> "Electro House", "edm" -> "EDM"."""
    palabras = []
    for palabra in genero.split():
        if palabra.lower() in SIGLAS:
            palabras.append(palabra.upper())
        else:
            palabras.append(palabra.title())
    return " ".join(palabras)


def style_tags_for(db: Session, artist: Artist) -> list[Tag]:
    """Convierte los generos del artista en etiquetas de estilo.

    Se crean en el catalogo como cualquier otra etiqueta, asi que despues se
    pueden renombrar o borrar a mano igual que las que escribe el usuario.
    """
    etiquetas: list[Tag] = []
    for genero in (artist.genres or [])[: settings.max_genres_per_artist]:
        nombre = genero.strip()
        if not nombre:
            continue
        slug = slugify(nombre)
        if not slug:
            continue
        etiqueta = tag_service.get_by_slug(db, TagKind.style, slug)
        if etiqueta is None:
            try:
                etiqueta = tag_service.create_tag(
                    db, kind=TagKind.style, name=genre_label(nombre)
                )
            except tag_service.TagError:
                continue
        etiquetas.append(etiqueta)
    return etiquetas


def apply_style_tags(db: Session, track: Track) -> list[Tag]:
    """Etiqueta una cancion con los estilos de sus artistas.

    Solo actua si la cancion no tiene ya alguna etiqueta de estilo: lo que haya
    puesto el usuario manda sobre lo que diga MusicBrainz.
    """
    if not settings.auto_style_tags:
        return []
    if any(t.kind == TagKind.style for t in track.tags):
        return []

    nuevas: list[Tag] = []
    vistas: set[int] = set()
    for artist in track.artists:
        for etiqueta in style_tags_for(db, artist):
            if etiqueta.id not in vistas:
                vistas.add(etiqueta.id)
                nuevas.append(etiqueta)
    # Con varios artistas se acumulaban hasta seis estilos por cancion, que ya
    # no clasifica nada. Se corta en el mismo tope que por artista.
    nuevas = nuevas[: settings.max_genres_per_artist]
    if nuevas:
        track.tags = [*track.tags, *nuevas]
    return nuevas


def get_by_id(db: Session, artist_id: int) -> Artist | None:
    return db.get(Artist, artist_id)


def get_by_slug(db: Session, slug: str) -> Artist | None:
    return db.scalar(select(Artist).where(Artist.slug == slug))


def get_or_create(db: Session, name: str) -> tuple[Artist, bool]:
    """Devuelve (artista, recien_creado). La unicidad va por slug, de modo que
    "Blur", "blur " y "BLUR" son el mismo artista."""
    name = name.strip()
    slug = slugify(name)
    if not slug:
        raise ValueError("Nombre de artista vacio.")

    existing = get_by_slug(db, slug)
    if existing is not None:
        return existing, False

    artist = Artist(name=name, slug=slug, enrichment_status=EnrichmentStatus.pending)
    db.add(artist)
    db.flush()
    link_pending_relations(db, artist)
    return artist, True


def link_pending_relations(db: Session, artist: Artist) -> int:
    """Conecta las relaciones que ya mencionaban a este artista por su nombre.

    "Robbie Williams -> miembro de Take That" se guarda con el nombre aunque
    Take That no este en la biblioteca. Cuando mas tarde aparece, esa relacion
    pasa a ser un enlace navegable. La comparacion la hace MariaDB con la
    colacion utf8mb4_unicode_ci, que ignora mayusculas y acentos.
    """
    huerfanas = list(
        db.scalars(
            select(ArtistRelation).where(
                ArtistRelation.related_artist_id.is_(None),
                ArtistRelation.related_name == artist.name,
                ArtistRelation.artist_id != artist.id,
            )
        )
    )
    for relation in huerfanas:
        relation.related_artist_id = artist.id
    return len(huerfanas)


def list_artists(
    db: Session, *, search: str | None = None, limit: int = 200, offset: int = 0
) -> tuple[list[Artist], int]:
    stmt = select(Artist)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(Artist.name.like(pattern), Artist.bio.like(pattern)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.order_by(Artist.name).limit(limit).offset(offset)))
    return rows, total


def link_track_artists(db: Session, track: Track) -> list[Artist]:
    """Crea o reutiliza las fichas de los artistas de una cancion y las vincula."""
    names = split_artist_names(track.artist_text)
    artists: list[Artist] = []
    for name in names:
        try:
            artist, _ = get_or_create(db, name)
        except ValueError:
            continue
        artists.append(artist)
    track.artists = artists
    return artists


def set_track_artists(db: Session, track: Track, names: list[str]) -> list[Artist]:
    artists: list[Artist] = []
    for name in names:
        artist, _ = get_or_create(db, name)
        artists.append(artist)
    track.artists = artists
    track.artist_text = ", ".join(a.name for a in artists) or None
    track.updated_at = utcnow()
    return artists


# --- Enriquecido ------------------------------------------------------------


def apply_facts(db: Session, artist: Artist, facts: ArtistFacts) -> Artist:
    """Vuelca en la ficha lo encontrado fuera, sin pisar lo que ya haya escrito
    el usuario a mano (esas fichas quedan en estado `manual`)."""
    artist.musicbrainz_id = facts.musicbrainz_id or artist.musicbrainz_id
    artist.country = facts.country or artist.country
    artist.begin_year = facts.begin_year or artist.begin_year
    artist.end_year = facts.end_year or artist.end_year
    artist.artist_type = facts.artist_type or artist.artist_type
    artist.bio = facts.bio or artist.bio
    artist.wikipedia_url = facts.wikipedia_url or artist.wikipedia_url
    artist.image_url = artist.image_url or facts.image_url
    if facts.links:
        artist.links = {**(artist.links or {}), **facts.links}
    if facts.genres:
        artist.genres = facts.genres

    existing = {(r.related_name.lower(), r.relation_type) for r in artist.relations}
    for relation in facts.relations:
        key = (relation.name.lower(), relation.relation_type)
        if key in existing:
            continue
        existing.add(key)
        artist.relations.append(
            ArtistRelation(
                related_name=relation.name,
                relation_type=relation.relation_type,
                related_musicbrainz_id=relation.musicbrainz_id,
                # Si ese artista tambien esta en la biblioteca, se enlazan
                related_artist_id=(
                    other.id if (other := get_by_slug(db, slugify(relation.name))) else None
                ),
            )
        )

    artist.enrichment_status = EnrichmentStatus.ok
    artist.enrichment_error = None
    artist.enriched_at = utcnow()
    artist.updated_at = utcnow()
    return artist


def apply_channel(db: Session, artist: Artist, *, set_status: bool = True) -> bool:
    """Respaldo para los creadores de mashups, edits y transiciones.

    MusicBrainz y Wikipedia documentan artistas publicados, no a quien monta un
    edit y lo sube a YouTube. Pero ese canal SI existe y tiene nombre, avatar y
    suscriptores, que es exactamente la informacion que falta en esas fichas.
    """
    video = next(
        (
            t.source_url
            for t in artist.tracks
            if t.source_url and t.source_site == "youtube" and t.status == TrackStatus.ready
        ),
        None,
    )
    if video is None:
        return False

    try:
        canal = downloader.channel_info(video)
    except downloader.DownloadError as exc:
        logger.info("No se pudo leer el canal de %s: %s", artist.name, exc)
        return False
    if canal is None:
        return False

    # Solo se rellena lo que este vacio: si Wikipedia dio algo, manda Wikipedia.
    artist.image_url = artist.image_url or canal.avatar_url
    artist.bio = artist.bio or canal.description
    artist.channel_url = canal.url
    artist.follower_count = canal.follower_count
    # Cuando el canal es lo unico que hay, el estado lo refleja. Si solo se ha
    # usado para tapar un hueco (una foto que faltaba), el estado no cambia:
    # los datos siguen siendo de MusicBrainz.
    if set_status:
        artist.enrichment_status = EnrichmentStatus.youtube
        artist.enrichment_error = None
    artist.enriched_at = utcnow()
    artist.updated_at = utcnow()
    return True


def apply_spotify_genres(artist: Artist) -> bool:
    """Rellena los generos desde Spotify cuando MusicBrainz no los tiene.

    Es justo el hueco de MusicBrainz: los urbanos recientes no estan
    catalogados alli, pero en Spotify si. No hace falta que nadie haya
    conectado su cuenta: los generos son catalogo publico.
    """
    if artist.genres or not spotify.is_enabled():
        return False
    try:
        generos = spotify.artist_genres(artist.name)
    except spotify.SpotifyError as exc:
        logger.info("No se pudieron pedir generos de %s a Spotify: %s", artist.name, exc)
        return False
    if not generos:
        return False
    artist.genres = generos
    artist.updated_at = utcnow()
    return True


def enrich(db: Session, artist: Artist, *, force: bool = False) -> Artist:
    """Consulta las fuentes externas y actualiza la ficha."""
    if artist.enrichment_status == EnrichmentStatus.manual and not force:
        return artist
    if not settings.enrichment_enabled:
        artist.enrichment_status = EnrichmentStatus.error
        artist.enrichment_error = "El enriquecido automatico esta desactivado."
        return artist

    try:
        facts = enrichment.lookup(artist.name)
    except EnrichmentError as exc:
        artist.enrichment_status = EnrichmentStatus.error
        artist.enrichment_error = str(exc)[:400]
        artist.updated_at = utcnow()
        return artist

    if facts is None:
        # Las bases de datos musicales no lo conocen. Antes de darlo por
        # perdido, se mira su canal de YouTube.
        if apply_channel(db, artist):
            apply_spotify_genres(artist)
            return artist
        artist.enrichment_status = EnrichmentStatus.not_found
        artist.enrichment_error = None
        artist.enriched_at = utcnow()
        artist.updated_at = utcnow()
        return artist

    apply_facts(db, artist, facts)

    # Las bases musicales conocen a muchos artistas de los que Wikipedia no
    # tiene articulo, y por tanto tampoco foto. Su canal de YouTube casi
    # siempre la tiene, asi que se usa para tapar ese hueco concreto.
    if not artist.image_url:
        apply_channel(db, artist, set_status=False)
    # MusicBrainz cataloga poco lo urbano reciente; Spotify si.
    apply_spotify_genres(artist)
    return artist


def run_enrichment(session_factory, artist_ids: list[int]) -> None:
    """Version para tareas en segundo plano: sesion propia y sin propagar
    errores, que una biografia que falta no debe romper nada."""
    for artist_id in artist_ids:
        try:
            with session_factory() as db:
                artist = db.get(Artist, artist_id)
                if artist is None or artist.enrichment_status in (
                    EnrichmentStatus.ok,
                    EnrichmentStatus.youtube,
                    EnrichmentStatus.manual,
                ):
                    continue
                enrich(db, artist)
                db.commit()
        except Exception:  # pragma: no cover - nunca tumbar la tarea de fondo
            logger.exception("Fallo enriqueciendo el artista %s", artist_id)
