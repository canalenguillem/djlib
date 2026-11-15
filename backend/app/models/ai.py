from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base


class AiKey(Base):
    """La clave de un usuario para un proveedor de IA (OpenAI, Anthropic,
    Grok). Cada uno paga lo suyo: la clave del servidor ya no se usa.

    La clave se guarda cifrada: quien vea la base de datos (una copia de
    seguridad, por ejemplo) no puede gastar con ella."""

    __tablename__ = "ai_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_ai_keys_user_provider"),
        {"mysql_engine": "InnoDB"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    api_key_cifrada: Mapped[str] = mapped_column(Text, nullable=False)
    # Los ultimos caracteres, para que el usuario reconozca cual puso
    pista: Mapped[str] = mapped_column(String(8), nullable=False)
    # Si no se pone, el de por defecto del proveedor
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )
