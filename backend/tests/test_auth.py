from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import login_rate_limiter
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, auth_headers, login


def test_login_correcto_devuelve_par_de_tokens(client: TestClient, admin_user) -> None:
    data = login(client, "enguillem", ADMIN_PASSWORD)
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == settings.access_token_expire_minutes * 60


def test_login_con_contrasena_incorrecta(client: TestClient, admin_user) -> None:
    response = client.post(
        "/auth/login", json={"username": "enguillem", "password": "noEsLaBuena123"}
    )
    assert response.status_code == 401


def test_login_con_usuario_inexistente(client: TestClient) -> None:
    response = client.post(
        "/auth/login", json={"username": "fantasma", "password": "loQueSea1234"}
    )
    assert response.status_code == 401


def test_login_de_usuario_desactivado(client: TestClient, normal_user, db) -> None:
    from app.models.user import User

    user = db.get(User, normal_user.id)
    user.is_active = False
    db.commit()

    response = client.post(
        "/auth/login", json={"username": "dj_pepe", "password": USER_PASSWORD}
    )
    assert response.status_code == 401


def test_rate_limit_tras_varios_fallos(client: TestClient, admin_user) -> None:
    login_rate_limiter.clear()
    for _ in range(settings.login_rate_limit_attempts):
        response = client.post(
            "/auth/login", json={"username": "enguillem", "password": "malaClave123"}
        )
        assert response.status_code == 401

    bloqueado = client.post(
        "/auth/login", json={"username": "enguillem", "password": ADMIN_PASSWORD}
    )
    assert bloqueado.status_code == 429
    assert "Retry-After" in bloqueado.headers


def test_me_sin_token_es_401(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401


def test_me_con_token_invalido_es_401(client: TestClient) -> None:
    response = client.get("/auth/me", headers=auth_headers("esto.no.es.un.jwt"))
    assert response.status_code == 401


def test_me_devuelve_el_usuario_autenticado(client: TestClient, admin_user) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    response = client.get("/auth/me", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "enguillem"
    assert body["role"] == "admin"
    assert "password_hash" not in body


def test_refresh_rota_el_token_y_el_antiguo_deja_de_valer(
    client: TestClient, admin_user
) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)

    renovado = client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert renovado.status_code == 200
    nuevos = renovado.json()
    assert nuevos["refresh_token"] != tokens["refresh_token"]

    reutilizado = client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reutilizado.status_code == 401

    # La reutilizacion revoca todas las sesiones, incluida la recien creada.
    assert (
        client.post("/auth/refresh", json={"refresh_token": nuevos["refresh_token"]}).status_code
        == 401
    )


def test_logout_revoca_el_refresh_token(client: TestClient, admin_user) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    assert (
        client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code
        == 204
    )
    assert (
        client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code
        == 401
    )


def test_cambio_de_contrasena_con_actual_incorrecta(client: TestClient, admin_user) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    response = client.patch(
        "/auth/me/password",
        json={"current_password": "meLaInvento123", "new_password": "NuevaClave1234"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 400


def test_cambio_de_contrasena_demasiado_corta(client: TestClient, admin_user) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    response = client.patch(
        "/auth/me/password",
        json={"current_password": ADMIN_PASSWORD, "new_password": "corta"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 400


def test_cambio_de_contrasena_correcto(client: TestClient, admin_user) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    nueva = "OtraClaveMejor2024"

    response = client.patch(
        "/auth/me/password",
        json={"current_password": ADMIN_PASSWORD, "new_password": nueva},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    nuevos = response.json()

    # El par devuelto sirve, el refresh anterior ya no, y la clave vieja falla.
    assert (
        client.get("/auth/me", headers=auth_headers(nuevos["access_token"])).status_code == 200
    )
    assert (
        client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login", json={"username": "enguillem", "password": ADMIN_PASSWORD}
        ).status_code
        == 401
    )
    login(client, "enguillem", nueva)


def test_cambio_de_contrasena_invalida_el_access_token_anterior(
    client: TestClient, admin_user
) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    import time

    time.sleep(1.1)  # el corte se compara con precision de segundos
    client.patch(
        "/auth/me/password",
        json={"current_password": ADMIN_PASSWORD, "new_password": "OtraClaveMejor2024"},
        headers=auth_headers(tokens["access_token"]),
    )
    response = client.get("/auth/me", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 401


def test_actualizar_email_propio(client: TestClient, normal_user) -> None:
    tokens = login(client, "dj_pepe", USER_PASSWORD)
    response = client.patch(
        "/auth/me/email",
        json={"email": "pepe@example.com"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["email"] == "pepe@example.com"


def test_email_duplicado_da_conflicto(client: TestClient, admin_user, normal_user) -> None:
    tokens = login(client, "dj_pepe", USER_PASSWORD)
    response = client.patch(
        "/auth/me/email",
        json={"email": admin_user.email},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 409
