"""Cada usuario pone sus claves de IA y elige cual se usa."""

from fastapi.testclient import TestClient

from app.models.ai import AiKey
from app.services import ai_keys
from tests.conftest import USER_PASSWORD, TestingSessionLocal, auth_headers, login
from tests.test_batches import headers


def proveedores(datos: dict) -> dict:
    return {p["id"]: p for p in datos["providers"]}


def test_poner_elegir_y_borrar(client: TestClient, admin_user) -> None:
    h = headers(client)
    datos = client.get("/me/ai", headers=h).json()
    assert datos["selected"] is None
    assert set(proveedores(datos)) == {"openai", "anthropic", "grok"}
    assert not any(p["configured"] for p in datos["providers"])

    # La primera clave queda elegida
    datos = client.put("/me/ai/anthropic", json={"api_key": "sk-ant-secreta-9876"}, headers=h).json()
    assert datos["selected"] == "anthropic"
    anthropic = proveedores(datos)["anthropic"]
    assert anthropic["configured"] and anthropic["key_hint"] == "9876"
    assert "secreta" not in str(datos)  # la clave nunca vuelve entera

    datos = client.put("/me/ai/grok", json={"api_key": "xai-otra-1111", "model": "grok-4-vision"}, headers=h).json()
    assert datos["selected"] == "anthropic"
    assert proveedores(datos)["grok"]["model"] == "grok-4-vision"

    datos = client.put("/me/ai/selected", json={"provider": "grok"}, headers=h).json()
    assert datos["selected"] == "grok"

    # Cambiar solo el modelo, sin volver a pegar la clave
    datos = client.put("/me/ai/grok", json={"model": ""}, headers=h).json()
    assert proveedores(datos)["grok"]["model"] is None
    assert proveedores(datos)["grok"]["key_hint"] == "1111"

    # Borrar la elegida pasa a la otra
    datos = client.delete("/me/ai/grok", headers=h).json()
    assert datos["selected"] == "anthropic"
    assert not proveedores(datos)["grok"]["configured"]


def test_la_clave_se_guarda_cifrada(client: TestClient, admin_user) -> None:
    client.put("/me/ai/openai", json={"api_key": "sk-muy-secreta-4242"}, headers=headers(client))
    with TestingSessionLocal() as db:
        guardada = db.query(AiKey).one()
        assert "sk-muy-secreta" not in guardada.api_key_cifrada
        user = db.get(type(admin_user), admin_user.id)
        conf = ai_keys.config(db, user)
        assert conf.api_key == "sk-muy-secreta-4242"
        assert conf.model == ai_keys.PROVEEDORES["openai"].modelo


def test_errores(client: TestClient, admin_user) -> None:
    h = headers(client)
    assert client.put("/me/ai/gemini", json={"api_key": "x"}, headers=h).status_code == 400
    assert client.put("/me/ai/openai", json={"api_key": ""}, headers=h).status_code == 400
    r = client.put("/me/ai/selected", json={"provider": "openai"}, headers=h)
    assert r.status_code == 400 and "Primero" in r.json()["detail"]


def test_cada_uno_ve_las_suyas(client: TestClient, admin_user, normal_user) -> None:
    client.put("/me/ai/openai", json={"api_key": "sk-del-admin-0000"}, headers=headers(client))
    pepe = auth_headers(login(client, "dj_pepe", USER_PASSWORD)["access_token"])
    datos = client.get("/me/ai", headers=pepe).json()
    assert datos["selected"] is None
    assert not proveedores(datos)["openai"]["configured"]


def test_probar_la_clave(client: TestClient, admin_user, monkeypatch) -> None:
    h = headers(client)
    client.put("/me/ai/openai", json={"api_key": "sk-prueba-5555"}, headers=h)
    vistas: list[ai_keys.AiConfig] = []

    def probar(conf):
        vistas.append(conf)
        raise ai_keys.AiKeyError("OpenAI no acepta esta clave.")

    monkeypatch.setattr(ai_keys, "probar", probar)
    r = client.post("/me/ai/openai/test", headers=h).json()
    assert r == {"ok": False, "message": "OpenAI no acepta esta clave."}
    assert vistas[0].api_key == "sk-prueba-5555"
    assert client.post("/me/ai/grok/test", headers=h).json()["ok"] is False
