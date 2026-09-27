from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI API Hub"
    app_base_url: str = "http://127.0.0.1:8000"
    secret_key: str = "dev-secret-change-me"
    database_url: str = "sqlite:///./data/hub.db"
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    provider_timeout: int = 60
    max_upload_mb: int = 5


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
