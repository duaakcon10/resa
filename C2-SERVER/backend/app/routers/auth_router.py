from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.auth import hash_password, verify_password, create_access_token, get_current_user
from app.database import get_db
from app.models.all_models import User
from app.schemas.all_schemas import LoginRequest, LoginResponse, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if user.is_banned: raise HTTPException(status.HTTP_403_FORBIDDEN, "Account banned")
    return LoginResponse(access_token=create_access_token(user.id, user.role), user_id=str(user.id), role=user.role)

@router.post("/register", response_model=UserOut)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where((User.username == data.username) | (User.email == data.email)))
    if existing.scalar_one_or_none(): raise HTTPException(409, "Username or email taken")
    user = User(username=data.username, email=data.email, password_hash=hash_password(data.password))
    db.add(user); await db.commit(); await db.refresh(user)
    return UserOut.model_validate(user)

@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)