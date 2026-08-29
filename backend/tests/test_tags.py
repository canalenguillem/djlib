from fastapi.testclient import TestClient

from tests.conftest import ADMIN_PASSWORD, auth_headers, login


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


def test_listar_etiquetas_sin_token_es_401(client: TestClient) -> None:
    assert client.get("/tags").status_code == 401


def test_crear_y_listar_etiquetas(client: TestClient, admin_user) -> None:
    h = headers(client)
    creada = client.post("/tags", json={"kind": "mood", "name": "Chill"}, headers=h)
    assert creada.status_code == 201, creada.text
    assert creada.json()["slug"] == "chill"

    client.post("/tags", json={"kind": "style", "name": "Britpop"}, headers=h)
    client.post("/tags", json={"kind": "moment", "name": "Warm-up"}, headers=h)

    todas = client.get("/tags", headers=h).json()
    assert len(todas) == 3
    solo_estilo = client.get("/tags?kind=style", headers=h).json()
    assert [t["name"] for t in solo_estilo] == ["Britpop"]


def test_etiquetas_equivalentes_dan_conflicto(client: TestClient, admin_user) -> None:
    h = headers(client)
    client.post("/tags", json={"kind": "style", "name": "Ochentas"}, headers=h)
    # Mismo slug tras normalizar acentos, mayusculas y espacios
    repetida = client.post("/tags", json={"kind": "style", "name": "  OCHENTAS "}, headers=h)
    assert repetida.status_code == 409


def test_mismo_nombre_en_categorias_distintas_si_se_permite(
    client: TestClient, admin_user
) -> None:
    h = headers(client)
    assert client.post("/tags", json={"kind": "mood", "name": "Oscuro"}, headers=h).status_code == 201
    assert client.post("/tags", json={"kind": "style", "name": "Oscuro"}, headers=h).status_code == 201


def test_renombrar_y_borrar_etiqueta(client: TestClient, admin_user) -> None:
    h = headers(client)
    tag_id = client.post("/tags", json={"kind": "mood", "name": "Chil"}, headers=h).json()["id"]

    renombrada = client.patch(f"/tags/{tag_id}", json={"name": "Chill"}, headers=h)
    assert renombrada.status_code == 200
    assert renombrada.json()["slug"] == "chill"

    assert client.delete(f"/tags/{tag_id}", headers=h).status_code == 204
    assert client.get("/tags", headers=h).json() == []
