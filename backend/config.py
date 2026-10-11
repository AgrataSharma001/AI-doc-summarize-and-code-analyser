"""Small, explicit configuration surface for the local MVP."""

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'docode.db').as_posix()}"
    frontend_dir: Path = PROJECT_ROOT / "Frontend"
    secure_cookies: bool = False  # Set true if the app is later served through HTTPS.
    session_lifetime_seconds: int = 7 * 24 * 60 * 60
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = Field(default="qwen3:1.7b", min_length=1)
    ollama_timeout_seconds: float = Field(default=60, gt=0, le=75)
    model_context_chars: int = Field(default=6000, ge=1600, le=8000)

    @field_validator("ollama_url")
    @classmethod
    def local_model_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment or parsed.port == 0):
            raise ValueError("Ollama must use a loopback HTTP origin")
        return value.rstrip("/")

    model_config = SettingsConfigDict(env_prefix="DOCODE_", env_file=".env", extra="ignore")
