from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "КБЖУЙ API"
    version: str = "0.1.0"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://kbzhuy:kbzhuy@localhost:5432/kbzhuy"
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "dev-secret-key-change-in-production"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # AI — cloud
    anthropic_api_key: str = ""
    ai_model: str = "claude-sonnet-4-6"

    # AI — local (Ollama)
    use_local_llm: bool = False
    local_llm_url: str = "http://localhost:11434/v1"
    local_llm_model: str = "qwen2.5:14b"

    # AI — GigaChat (Sber)
    # Toggle on/off without changing code — just set USE_GIGACHAT=true/false
    use_gigachat: bool = False
    gigachat_credentials: str = ""   # base64(clientId:clientSecret) from Sber Studio
    gigachat_model: str = "GigaChat"  # GigaChat | GigaChat-Plus | GigaChat-Pro

    # CORS
    allowed_origins: list[str] = ["http://localhost:8081", "http://localhost:19006"]

    class Config:
        env_file = ".env"
        env_prefix = "KBZHUY_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
