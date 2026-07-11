from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from redis.asyncio import Redis
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=20, max_overflow=10)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
class Base(DeclarativeBase): pass

async def get_db() -> AsyncSession:
    async with async_session() as s:
        try: yield s
        finally: await s.close()

redis_client: Redis = None
async def init_redis():
    global redis_client
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis_client.ping()
async def close_redis():
    if redis_client: await redis_client.close()
async def get_redis() -> Redis: return redis_client