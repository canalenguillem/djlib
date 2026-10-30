import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class Menu(str, enum.Enum):
    """Apartados del menu que se dan o se quitan a cada usuario. "Mi cuenta"
    no esta: cada uno tiene que poder cambiar su contrasena."""

    library = "library"
    recognize = "recognize"
    mixer = "mixer"
    spotify = "spotify"
    beatport = "beatport"
    youtube = "youtube"
    charts = "charts"
    crates = "crates"
    downloads = "downloads"
    listen = "listen"
    artists = "artists"
    tags = "tags"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
        default=UserRole.user,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Lista de Menu que puede ver; None es todos
    menus: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    # Cualquier access token emitido antes de esta fecha deja de valer.
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.admin

    def can_use(self, menu: "Menu") -> bool:
        # El admin lo ve todo: si no, podria quitarse a si mismo el acceso
        return self.is_admin or self.menus is None or menu.value in self.menus

    @property
    def visible_menus(self) -> list["Menu"]:
        return [m for m in Menu if self.can_use(m)]

    def __repr__(self) -> str:  # pragma: no cover - ayuda al depurar
        return f"<User {self.id} {self.username} {self.role.value}>"
