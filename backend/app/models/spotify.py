from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base


class SpotifyAccount(Base):
    """La cuenta de Spotify enlazada por un usuario.

    Se guarda el refresh token, que es lo que permite seguir consultando sin
    volver a pedirle permiso. El access token dura una hora y se renueva solo.
    """

    __tablename__ = "spotify_accounts"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    spotify_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scope: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    user: Mapped["User"] = relationship()  # noqa: F821

    def token_vigente(self) -> bool:
        return bool(
            self.access_token
            and self.expires_at
            # Margen de un minuto: no vale la pena usar un token que expira ya
            and (self.expires_at - utcnow()).total_seconds() > 60
        )
