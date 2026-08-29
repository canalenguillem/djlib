import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import settings


class LoginRateLimiter:
    """Limitador en memoria por IP para /auth/login.

    Cuenta solo los intentos FALLIDOS: un login correcto limpia el contador,
    de modo que un usuario legitimo nunca se autobloquea. Al vivir en memoria
    se reinicia con el proceso y no se comparte entre replicas; suficiente
    para frenar fuerza bruta en un despliegue de un solo backend.
    """

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        attempts = self._attempts[key]
        while attempts and now - attempts[0] > self.window_seconds:
            attempts.popleft()
        return attempts

    def retry_after(self, key: str) -> int | None:
        """Segundos que faltan para poder reintentar, o None si puede pasar."""
        now = time.monotonic()
        with self._lock:
            attempts = self._prune(key, now)
            if len(attempts) < self.max_attempts:
                return None
            return max(1, int(self.window_seconds - (now - attempts[0])))

    def register_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._attempts.clear()


login_rate_limiter = LoginRateLimiter(
    max_attempts=settings.login_rate_limit_attempts,
    window_seconds=settings.login_rate_limit_window_seconds,
)


def client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
