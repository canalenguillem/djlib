from datetime import datetime, timezone


def utcnow() -> datetime:
    """UTC "naive": MariaDB guarda DATETIME sin zona horaria, asi que
    trabajamos siempre en UTC sin tzinfo para no mezclar tipos al comparar."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_epoch(dt: datetime) -> float:
    return dt.replace(tzinfo=timezone.utc).timestamp()
