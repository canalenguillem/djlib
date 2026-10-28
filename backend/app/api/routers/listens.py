from datetime import timedelta

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.core.time import utcnow
from app.models.listen import Listen, ListenSource
from app.models.track import Track
from app.models.user import User
from app.schemas.listen import ListenCounts, ListenCreate, ListenStats, TopTrack, UserListens

router = APIRouter(prefix="/listens", tags=["listens"])

# Lo que se ensena en la lista de canciones mas escuchadas
TOP = 10


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def register_listen(payload: ListenCreate, current_user: CurrentUser, db: DbSession) -> Response:
    """El navegador avisa cuando una cancion lleva el rato suficiente sonando:
    cargarla o darle al play un segundo no cuenta."""
    if db.get(Track, payload.track_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cancion no encontrada.")
    db.add(Listen(user_id=current_user.id, track_id=payload.track_id, source=payload.source))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/stats", response_model=ListenStats)
def listen_stats(admin: AdminUser, db: DbSession) -> ListenStats:
    hace_una_semana = utcnow() - timedelta(days=7)
    reciente = Listen.created_at >= hace_una_semana

    filas = db.execute(
        select(
            Listen.user_id,
            Listen.source,
            func.count(),
            func.sum(func.if_(reciente, 1, 0)),
            func.max(Listen.created_at),
        ).group_by(Listen.user_id, Listen.source)
    ).all()

    por_usuario: dict[int | None, UserListens] = {}
    for user_id, source, total, semana, ultima in filas:
        fila = por_usuario.setdefault(
            user_id,
            UserListens(
                user_id=user_id,
                username=None,
                total=ListenCounts(),
                last_7_days=ListenCounts(),
                last_listen_at=None,
            ),
        )
        setattr(fila.total, source.value, total)
        setattr(fila.last_7_days, source.value, int(semana or 0))
        if fila.last_listen_at is None or ultima > fila.last_listen_at:
            fila.last_listen_at = ultima

    nombres = dict(db.execute(select(User.id, User.username)).all())
    for fila in por_usuario.values():
        fila.username = nombres.get(fila.user_id)
    usuarios = sorted(
        por_usuario.values(), key=lambda f: f.total.player + f.total.mixer, reverse=True
    )

    en_reproductor = func.sum(func.if_(Listen.source == ListenSource.player, 1, 0))
    en_mezclador = func.sum(func.if_(Listen.source == ListenSource.mixer, 1, 0))
    top = db.execute(
        select(Track.id, Track.title, Track.artist_text, en_reproductor, en_mezclador)
        .join(Listen, Listen.track_id == Track.id)
        .group_by(Track.id, Track.title, Track.artist_text)
        .order_by(func.count().desc(), Track.id)
        .limit(TOP)
    ).all()

    return ListenStats(
        users=usuarios,
        top_tracks=[
            TopTrack(track_id=i, title=t, artist_text=a, player=int(p or 0), mixer=int(m or 0))
            for i, t, a, p, m in top
        ],
    )
