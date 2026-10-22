from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    # Usuario o correo, por eso admite la longitud de un correo
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class GoogleLoginRequest(BaseModel):
    # El ID token que devuelve el boton de Google
    credential: str = Field(min_length=1, max_length=4096)


class AuthConfig(BaseModel):
    google_client_id: str | None


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
