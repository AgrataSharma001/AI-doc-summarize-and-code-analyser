"""Small, explicit configuration surface for the local MVP."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'docode.db').as_posix()}"
    frontend_dir: Path = PROJECT_ROOT / "Frontend"
    secure_cookies: bool = False  # Set true if the app is later served through HTTPS.
    session_lifetime_seconds: int = 7 * 24 * 60 * 60

    model_config = SettingsConfigDict(env_prefix="DOCODE_", env_file=".env", extra="ignore")
