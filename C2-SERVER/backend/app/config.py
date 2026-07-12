from pydantic_settings import BaseSettings
from typing import Optional

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
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_ADMIN_CHAT_ID: Optional[int] = None
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    # MB Bank — credentials for mbbank-service
    MB_USERNAME: Optional[str] = None
    MB_PASSWORD: Optional[str] = None
    MB_ACCOUNT_NUMBER: Optional[str] = None
    MB_ACCOUNT_NAME: Optional[str] = None
    MB_SERVICE_URL: str = "http://mbbank:3000"
    MB_SERVICE_API_KEY: str = "c2-mb-internal-key"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
