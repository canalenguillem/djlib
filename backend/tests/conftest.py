from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registra los modelos en Base.metadata)
from app.core.config import settings
from app.core.rate_limit import login_rate_limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app
from app.models.user import User, UserRole
from app.services import user_service

# Los tests corren contra una base MariaDB aparte ("<db>_test"), creada por el
# script de init del contenedor de MariaDB. Asi se prueba el mismo motor que
# usa produccion (ENUM, colaciones, unicidad) y no un SQLite parecido.
engine = create_engine(settings.test_database_url, pool_pre_ping=True, future=True)
TestingSessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)

ADMIN_PASSWORD = "AdminPass1234"
USER_PASSWORD = "UserPass1234"


@pytest.fixture(autouse=True)
def fresh_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    login_rate_limiter.clear()
    yield
    login_rate_limiter.clear()


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


def _make_user(**kwargs) -> User:
    session = TestingSessionLocal()
    try:
        user = user_service.create_user(session, **kwargs)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user
    finally:
        session.close()


@pytest.fixture
def admin_user() -> User:
    return _make_user(
        username="enguillem",
        password=ADMIN_PASSWORD,
        email="admin@example.com",
        role=UserRole.admin,
    )


@pytest.fixture
def normal_user() -> User:
    return _make_user(username="dj_pepe", password=USER_PASSWORD, role=UserRole.user)


def login(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
