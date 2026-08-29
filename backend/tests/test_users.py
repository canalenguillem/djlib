from fastapi.testclient import TestClient

from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, auth_headers, login


def test_listar_usuarios_sin_token_es_401(client: TestClient) -> None:
    assert client.get("/users").status_code == 401


def test_listar_usuarios_sin_rol_admin_es_403(client: TestClient, normal_user) -> None:
    tokens = login(client, "dj_pepe", USER_PASSWORD)
    response = client.get("/users", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 403


def test_crear_usuario_sin_rol_admin_es_403(client: TestClient, normal_user) -> None:
    tokens = login(client, "dj_pepe", USER_PASSWORD)
    response = client.post(
        "/users",
        json={"username": "nuevo", "password": "ClaveNueva123", "role": "user"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 403


def test_admin_lista_usuarios(client: TestClient, admin_user, normal_user) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    response = client.get("/users", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    usernames = [u["username"] for u in response.json()]
    assert set(usernames) == {"enguillem", "dj_pepe"}


def test_admin_da_de_alta_usuario_que_luego_puede_entrar(
    client: TestClient, admin_user
) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    response = client.post(
        "/users",
        json={
            "username": "dj_nuevo",
            "email": "nuevo@example.com",
            "password": "ClaveInicial123",
            "role": "user",
        },
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 201, response.text
    creado = response.json()
    assert creado["username"] == "dj_nuevo"
    assert creado["role"] == "user"
    assert creado["is_active"] is True

    login(client, "dj_nuevo", "ClaveInicial123")


def test_alta_con_username_duplicado_da_conflicto(
    client: TestClient, admin_user, normal_user
) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    response = client.post(
        "/users",
        json={"username": "dj_pepe", "password": "ClaveInicial123"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 409


def test_alta_con_contrasena_corta_da_400(client: TestClient, admin_user) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    response = client.post(
        "/users",
        json={"username": "dj_corto", "password": "abc"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 400


def test_admin_desactiva_usuario_y_este_pierde_el_acceso(
    client: TestClient, admin_user, normal_user
) -> None:
    admin_tokens = login(client, "enguillem", ADMIN_PASSWORD)
    user_tokens = login(client, "dj_pepe", USER_PASSWORD)

    response = client.patch(
        f"/users/{normal_user.id}",
        json={"is_active": False},
        headers=auth_headers(admin_tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    assert client.get("/auth/me", headers=auth_headers(user_tokens["access_token"])).status_code == 401
    assert (
        client.post("/auth/refresh", json={"refresh_token": user_tokens["refresh_token"]}).status_code
        == 401
    )
    assert (
        client.post("/auth/login", json={"username": "dj_pepe", "password": USER_PASSWORD}).status_code
        == 401
    )


def test_admin_cambia_el_rol_de_otro_usuario(
    client: TestClient, admin_user, normal_user
) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    response = client.patch(
        f"/users/{normal_user.id}",
        json={"role": "admin"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_admin_no_puede_desactivarse_a_si_mismo(client: TestClient, admin_user) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    response = client.patch(
        f"/users/{admin_user.id}",
        json={"is_active": False},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 400


def test_admin_no_puede_cambiar_su_propio_rol(client: TestClient, admin_user) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    response = client.patch(
        f"/users/{admin_user.id}",
        json={"role": "user"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 400


def test_patch_de_usuario_inexistente_es_404(client: TestClient, admin_user) -> None:
    tokens = login(client, "enguillem", ADMIN_PASSWORD)
    response = client.patch(
        "/users/9999",
        json={"is_active": False},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
