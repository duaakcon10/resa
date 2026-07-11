from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://c2_admin:changeme@localhost:5432/c2_db"
    REDIS_URL: str = "redis://localhost:6379"
    JWT_SECRET: str = "super-secret-change-me-to-random-64-char-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    C2_HOST: str = "0.0.0.0"
    C2_PORT: int = 443
    C2_DOMAIN: str = "api.your-domain.com"
    DASHBOARD_URL: str = "https://your-domain.com"
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_ADMIN_CHAT_ID: Optional[int] = None
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    MB_USERNAME: Optional[str] = None
    MB_PASSWORD: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    class Config: env_file = ".env"

settings = Settings()