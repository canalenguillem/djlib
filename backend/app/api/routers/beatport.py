from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession, require_menu
from app.core.text import normalize_key
from app.models.track import Track, TrackStatus
from app.models.user import Menu
from app.schemas.beatport import BeatportGenre, BeatportTop, BeatportTrackOut
from app.services import beatport
from app.services.beatport import BeatportError

router = APIRouter(
    prefix="/beatport", tags=["beatport"], dependencies=[require_menu(Menu.beatport)]
)


@router.get("/genres", response_model=list[BeatportGenre])
def beatport_genres(current_user: CurrentUser) -> list[BeatportGenre]:
    return [BeatportGenre(id=i, name=nombre) for i, nombre, _ in beatport.GENEROS]


@router.get("/top-100", response_model=BeatportTop)
def beatport_top100(
    current_user: CurrentUser, db: DbSession, genre: int | None = Query(default=None)
) -> BeatportTop:
    try:
        pistas = beatport.top100(genre)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BeatportError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    # La mezcla va entre parentesis y la clave los ignora: "Zoolander" y
    # "Zoolander (Extended Mix)" cuentan como la misma
    claves = {normalize_key(p.artist, p.title) for p in pistas}
    existentes = (
        set(
            db.scalars(
                Track.__table__.select()
                .with_only_columns(Track.normalized_key)
                .where(
                    Track.normalized_key.in_(list(claves)),
                    Track.status.in_(
                        (TrackStatus.ready, TrackStatus.pending, TrackStatus.downloading)
                    ),
                )
            )
        )
        if claves
        else set()
    )
    nombre = next((n for i, n, _ in beatport.GENEROS if i == genre), None)
    return BeatportTop(
        genre=BeatportGenre(id=genre, name=nombre) if genre is not None and nombre else None,
        items=[
            BeatportTrackOut(
                position=p.position,
                title=f"{p.title} ({p.mix})" if p.mix else p.title,
                name=p.title,
                mix=p.mix,
                artist=p.artist,
                remixers=p.remixers,
                bpm=p.bpm,
                key=p.key,
                genre=p.genre,
                label=p.label,
                length=p.length,
                release_date=p.release_date,
                image_url=p.image_url,
                sample_url=p.sample_url,
                beatport_url=p.beatport_url,
                already_in_library=normalize_key(p.artist, p.title) in existentes,
            )
            for p in pistas
        ],
    )
