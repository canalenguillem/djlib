from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession, SessionFactory
from app.core.text import slugify
from app.core.time import utcnow
from app.models.artist import EnrichmentStatus
from app.schemas.artist import ArtistCreate, ArtistOut, ArtistPage, ArtistUpdate
from app.schemas.track import TrackOut
from app.services import artist_service

router = APIRouter(prefix="/artists", tags=["artists"])


def _to_out(artist) -> ArtistOut:
    out = ArtistOut.model_validate(artist)
    out.track_count = len(artist.tracks)
    return out


def _get_or_404(db, artist_id: int):
    artist = artist_service.get_by_id(db, artist_id)
    if artist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artista no encontrado.")
    return artist


@router.get("", response_model=ArtistPage)
def list_artists(
    current_user: CurrentUser,
    db: DbSession,
    search: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ArtistPage:
    items, total = artist_service.list_artists(db, search=search, limit=limit, offset=offset)
    return ArtistPage(
        items=[_to_out(a) for a in items], total=total, limit=limit, offset=offset
    )


@router.post("", response_model=ArtistOut, status_code=status.HTTP_201_CREATED)
def create_artist(
    payload: ArtistCreate,
    background: BackgroundTasks,
    current_user: CurrentUser,
    db: DbSession,
    session_factory: SessionFactory,
) -> ArtistOut:
    existing = artist_service.get_by_slug(db, slugify(payload.name))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{existing.name}' ya esta en la biblioteca.",
        )
    try:
        artist, _ = artist_service.get_or_create(db, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(artist)
    result = _to_out(artist)
    background.add_task(artist_service.run_enrichment, session_factory, [artist.id])
    return result


@router.get("/{artist_id}", response_model=ArtistOut)
def get_artist(artist_id: int, current_user: CurrentUser, db: DbSession) -> ArtistOut:
    return _to_out(_get_or_404(db, artist_id))


@router.get("/{artist_id}/tracks", response_model=list[TrackOut])
def get_artist_tracks(artist_id: int, current_user: CurrentUser, db: DbSession):
    artist = _get_or_404(db, artist_id)
    return [TrackOut.model_validate(t) for t in artist.tracks]


@router.patch("/{artist_id}", response_model=ArtistOut)
def update_artist(
    artist_id: int, payload: ArtistUpdate, current_user: CurrentUser, db: DbSession
) -> ArtistOut:
    artist = _get_or_404(db, artist_id)
    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"]:
        nuevo_slug = slugify(data["name"])
        clash = artist_service.get_by_slug(db, nuevo_slug)
        if clash is not None and clash.id != artist.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un artista llamado '{clash.name}'.",
            )
        artist.name = data["name"].strip()
        artist.slug = nuevo_slug

    for campo in ("bio", "country", "wikipedia_url"):
        if campo in data:
            valor = (data[campo] or "").strip()
            setattr(artist, campo, valor or None)
    for campo in ("begin_year", "end_year"):
        if campo in data:
            setattr(artist, campo, data[campo])

    # A partir de una edicion manual, el enriquecido automatico no pisa la ficha.
    artist.enrichment_status = EnrichmentStatus.manual
    artist.enrichment_error = None
    artist.updated_at = utcnow()
    db.commit()
    db.refresh(artist)
    return _to_out(artist)


@router.post("/{artist_id}/enrich", response_model=ArtistOut)
def enrich_artist(
    artist_id: int,
    current_user: CurrentUser,
    db: DbSession,
    force: bool = Query(default=False, description="Rehacer aunque la ficha sea manual"),
) -> ArtistOut:
    """Vuelve a consultar MusicBrainz y Wikipedia. Sincrono a proposito: lo
    lanza el usuario desde la ficha y quiere ver el resultado."""
    artist = _get_or_404(db, artist_id)
    artist_service.enrich(db, artist, force=force)
    db.commit()
    db.refresh(artist)
    return _to_out(artist)


@router.delete("/{artist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_artist(artist_id: int, current_user: CurrentUser, db: DbSession) -> Response:
    artist = _get_or_404(db, artist_id)
    db.delete(artist)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
