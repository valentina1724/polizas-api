"""Configuración del servicio, leída del entorno y de `.env` (nunca del código)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///app.db"
    # Los secretos no tienen valor real por defecto: llegan por .env o por variable de entorno.
    secreto_firma: str = ""
    clave_api_reaseguro: str = ""
    ruta_modelo: str = "modelo.pkl"
    umbral_alto_riesgo: float = 0.6


@lru_cache
def get_settings() -> Settings:
    """Lee el entorno una sola vez y reutiliza el mismo objeto en cada petición."""
    return Settings()
