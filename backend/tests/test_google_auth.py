import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import login_rate_limiter
from app.services import google_auth
from tests.conftest import auth_headers

CLIENT_ID = "1234-prueba.apps.googleusercontent.com"
# Hace de Google: firma los tokens y su clave publica es la que se comprueba
CLAVE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def google(monkeypatch):
    login_rate_limiter.clear()
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    jwks = SimpleNamespace(get_signing_key_from_jwt=lambda _t: SimpleNamespace(key=CLAVE.public_key()))
    monkeypatch.setattr(google_auth, "_client", lambda: jwks)


def token(clave=CLAVE, **cambios) -> str:
    ahora = int(time.time())
    datos = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1000",
        "email": "admin@example.com",
        "email_verified": True,
        "iat": ahora,
        "exp": ahora + 600,
    }
    datos.update(cambios)
    return jwt.encode(datos, clave, algorithm="RS256")


def entrar(client: TestClient, credential: str):
    return client.post("/auth/google", json={"credential": credential})


def test_config_da_el_id_de_cliente(client: TestClient, monkeypatch) -> None:
    assert client.get("/auth/config").json() == {"google_client_id": CLIENT_ID}
    monkeypatch.setattr(settings, "google_client_id", "")
    assert client.get("/auth/config").json() == {"google_client_id": None}


def test_entra_el_usuario_con_ese_correo(client: TestClient, admin_user) -> None:
    respuesta = entrar(client, token(email="Admin@Example.com"))
    assert respuesta.status_code == 200, respuesta.text
    me = client.get("/auth/me", headers=auth_headers(respuesta.json()["access_token"]))
    assert me.json()["username"] == "enguillem"


@pytest.mark.parametrize(
    "credential",
    [
        lambda: token(email_verified=False),
        lambda: token(aud="otra-app.apps.googleusercontent.com"),
        lambda: token(iss="https://malo.example.com"),
        lambda: token(exp=int(time.time()) - 60),
        lambda: token(clave=rsa.generate_private_key(public_exponent=65537, key_size=2048)),
        lambda: "esto.no.es.un.jwt",
    ],
    ids=["sin_verificar", "otra_app", "otro_emisor", "caducado", "otra_firma", "basura"],
)
def test_rechaza_tokens_que_no_valen(client: TestClient, admin_user, credential) -> None:
    assert entrar(client, credential()).status_code == 401


def test_usuario_desactivado_no_entra(client: TestClient, admin_user, db) -> None:
    from app.models.user import User

    db.get(User, admin_user.id).is_active = False
    db.commit()
    assert entrar(client, token()).status_code == 403


def test_correo_nuevo_queda_pendiente_hasta_que_lo_aprueben(client: TestClient, admin_user, db) -> None:
    from app.models.user import User, UserRole
    from app.services import user_service

    # Ya hay alguien llamado "pau": el nuevo se llama de otra forma
    user_service.create_user(db, username="pau", password="UnaClaveLarga123")
    db.commit()

    assert entrar(client, token(email="pau@gmail.com")).status_code == 403
    nuevo = user_service.get_by_email(db, "pau@gmail.com")
    assert nuevo.username == "pau2"
    assert nuevo.is_active is False
    assert nuevo.role == UserRole.user

    # Volver a intentarlo no crea otro
    assert entrar(client, token(email="pau@gmail.com")).status_code == 403
    assert db.query(User).filter(User.email == "pau@gmail.com").count() == 1

    db.get(User, nuevo.id).is_active = True
    db.commit()
    respuesta = entrar(client, token(email="pau@gmail.com"))
    assert respuesta.status_code == 200
    me = client.get("/auth/me", headers=auth_headers(respuesta.json()["access_token"]))
    assert me.json()["username"] == "pau2"


def test_token_malo_no_crea_usuario(client: TestClient, admin_user, db) -> None:
    from app.services import user_service

    entrar(client, token(email="intruso@gmail.com", email_verified=False))
    assert user_service.get_by_email(db, "intruso@gmail.com") is None


def test_sin_configurar_no_entra_nadie(client: TestClient, admin_user, monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", "")
    assert entrar(client, token()).status_code == 401
