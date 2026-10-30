from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession, require_menu
from app.models.track import Track, TrackStatus
from app.models.user import Menu
from app.schemas.charts import (
    ChartCombined,
    ChartError,
    ChartPosition,
    ChartSource,
    ChartTrackOut,
)
from app.services import charts

router = APIRouter(prefix="/charts", tags=["charts"], dependencies=[require_menu(Menu.charts)])


@router.get("/sources", response_model=list[ChartSource])
def chart_sources(current_user: CurrentUser) -> list[ChartSource]:
    return [ChartSource(id=f.id, name=f.name, group=f.group) for f in charts.fuentes()]


@router.get("/combined", response_model=ChartCombined)
def chart_combined(
    current_user: CurrentUser,
    db: DbSession,
    sources: list[str] = Query(default=[], alias="source"),
    limit: int = Query(default=100, ge=1, le=500),
) -> ChartCombined:
    try:
        listas, errores = charts.leer(sources)
    except charts.ChartError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not listas:
        # Todas han fallado: no hay nada que ensenar
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=next(iter(errores.values()))
        )

    combinadas = charts.combinar(listas, sources)[:limit]
    claves = set().union(*(c.claves for c in combinadas)) if combinadas else set()
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
    return ChartCombined(
        items=[
            ChartTrackOut(
                title=f"{c.entrada.name} ({c.entrada.mix})" if c.entrada.mix else c.entrada.name,
                name=c.entrada.name,
                mix=c.entrada.mix,
                artist=c.entrada.artist,
                bpm=c.entrada.bpm,
                key=c.entrada.key,
                duration_seconds=c.entrada.duration_seconds,
                image_url=c.entrada.image_url,
                sample_url=c.entrada.sample_url,
                url=c.entrada.url,
                positions=[ChartPosition(source=f, position=p) for f, p in c.posiciones],
                score=round(c.score, 2),
                already_in_library=bool(c.claves & existentes),
            )
            for c in combinadas
        ],
        errors=[ChartError(source=f, message=m) for f, m in errores.items()],
    )
