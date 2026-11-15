from pydantic import BaseModel, Field


class AiProviderOut(BaseModel):
    id: str
    name: str
    default_model: str
    console_url: str
    configured: bool
    # Los ultimos caracteres de la clave guardada; nunca la clave entera
    key_hint: str | None = None
    model: str | None = None


class AiSettings(BaseModel):
    selected: str | None
    providers: list[AiProviderOut]


class AiKeyIn(BaseModel):
    # Vacia para cambiar solo el modelo de una clave que ya esta
    api_key: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=100)


class AiSelect(BaseModel):
    provider: str = Field(max_length=20)


class AiTestResult(BaseModel):
    ok: bool
    message: str
