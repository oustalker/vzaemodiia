"""Налаштування застосунку. Читаються зі змінних оточення."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    def __init__(self) -> None:
        self.app_name: str = "Взаємодія"
        self.env: str = os.getenv("APP_ENV", "development")
        self.database_url: str = os.getenv(
            "DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'vzaemodiia.db'}"
        )
        # У продакшені ключ ОБОВʼЯЗКОВО задається через оточення.
        self.secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
        self.jwt_algorithm: str = "HS256"
        self.access_token_ttl_minutes: int = int(os.getenv("ACCESS_TOKEN_TTL", "10080"))
        self.static_dir: Path = BASE_DIR / "static"
        # У розробці дозволяємо будь-яке походження, у продакшені — лише перелічені.
        origins = os.getenv("CORS_ORIGINS", "*")
        self.cors_origins: list[str] = [o.strip() for o in origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_insecure_secret(self) -> bool:
        return self.secret_key == "dev-secret-change-me"

    def validate(self) -> None:
        """У продакшені краще не піднятись, ніж піднятись із ключем із прикладу."""
        if not self.is_production:
            return
        if self.is_insecure_secret:
            raise RuntimeError("APP_ENV=production вимагає власного SECRET_KEY")
        if "*" in self.cors_origins:
            raise RuntimeError("APP_ENV=production вимагає явного списку CORS_ORIGINS")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
