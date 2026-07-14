from pydantic_settings import BaseSettings
from typing import Optional, List
import warnings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://c2_admin:changeme@localhost:5432/c2_db"
    REDIS_URL: str = "redis://localhost:6379"
    JWT_SECRET: str = "super-secret-change-me-to-random-64-char-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    C2_HOST: str = "0.0.0.0"
    C2_PORT: int = 8000
    C2_DOMAIN: str = "bot.minhvuong.io.vn"
    DASHBOARD_URL: str = "https://bot.minhvuong.io.vn"
    WEBSITE_URL: str = "https://bot.minhvuong.io.vn"
    # Comma-separated origins; empty = allow dashboard domain only
    CORS_ORIGINS: str = ""
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_ADMIN_CHAT_ID: Optional[int] = None
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    MB_USERNAME: Optional[str] = None
    MB_PASSWORD: Optional[str] = None
    MB_ACCOUNT_NUMBER: Optional[str] = None
    MB_ACCOUNT_NAME: Optional[str] = None
    # Docker: http://mbbank:3000 | local host: http://127.0.0.1:3000 (never 0.0.0.0 as client URL)
    MB_SERVICE_URL: str = "http://127.0.0.1:3000"
    MB_SERVICE_API_KEY: str = "c2-mb-internal-key"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"

    def cors_origin_list(self) -> List[str]:
        if self.CORS_ORIGINS.strip():
            return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        # Default: dashboard origin only (not "*")
        return [self.DASHBOARD_URL.rstrip("/")]

settings = Settings()
_weak = ("super-secret", "change-me", "changeme", "secret")
if any(w in (settings.JWT_SECRET or "").lower() for w in _weak) or len(settings.JWT_SECRET or "") < 32:
    warnings.warn(
        "JWT_SECRET is weak/default — set a long random JWT_SECRET in .env for production",
        stacklevel=1,
    )
