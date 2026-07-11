from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings
from app.database import get_db
from app.models.all_models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

def hash_password(pw: str) -> str: return pwd_context.hash(pw)
def verify_password(plain: str, hashed: str) -> bool: return pwd_context.verify(plain, hashed)

def create_access_token(user_id: UUID, role: str) -> str:
    payload = {"sub": str(user_id), "role": role, "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES), "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    try: return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError: return None

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security), db: AsyncSession = Depends(get_db)) -> User:
    if credentials is None: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing credentials")
    token = credentials.credentials
    payload = decode_token(token)
    if payload:
        result = await db.execute(select(User).where(User.id == payload.get("sub")))
        user = result.scalar_one_or_none()
        if user and not user.is_banned: return user
    result = await db.execute(select(User).where(User.api_key == token))
    user = result.scalar_one_or_none()
    if user and not user.is_banned: return user
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin": raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return current_user