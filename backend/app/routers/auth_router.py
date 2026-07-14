from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from app.auth import create_access_token, verify_password, get_current_user
from app.config import settings
from app.database import get_db, async_session
from app.models.all_models import User, TelegramSession
from app.schemas.all_schemas import LoginResponse, UserOut
from pydantic import BaseModel, EmailStr
from typing import Optional
import secrets, aiohttp

router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory tokens: token_str -> {state, telegram_id, expires, username}
# state: "pending" → "verified" (after bot confirms)
_pending_tokens: dict = {}
_admin_codes: dict = {}


class InitLoginRequest(BaseModel):
    telegram_username: Optional[str] = None  # optional, not required


class CheckLoginRequest(BaseModel):
    token: str


class TelegramLoginRequest(BaseModel):
    code: str


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminVerifyRequest(BaseModel):
    email: EmailStr
    code: str


@router.post("/telegram/init")
async def init_telegram_login(data: InitLoginRequest):
    """Step 1: Generate token + deep link. No username needed — bot sends it on verify."""
    token = secrets.token_urlsafe(24)
    _pending_tokens[token] = {
        "state": "pending",
        "telegram_username": data.telegram_username or "",
        "telegram_id": None,
        "expires": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    bot_username = settings.TELEGRAM_BOT_USERNAME or "atk_vip_bot"
    deep_link = f"https://telegram.me/{bot_username}?start={token}"
    return {
        "token": token,
        "deep_link": deep_link,
        "expires_in": 600,
    }


@router.post("/telegram/verify-bot")
async def verify_via_bot(data: dict):
    """Called BY the Telegram bot when user clicks the deep link.
    Bot sends: {token, telegram_id, telegram_username}"""
    token = data.get("token", "")
    tid = data.get("telegram_id", 0)
    tname = data.get("telegram_username", "")

    entry = _pending_tokens.get(token)
    if not entry:
        raise HTTPException(404, "Token not found")
    if entry["expires"] < datetime.now(timezone.utc):
        _pending_tokens.pop(token, None)
        raise HTTPException(410, "Token expired")

    # Mark as verified
    entry["state"] = "verified"
    entry["telegram_id"] = tid
    entry["telegram_username"] = tname
    return {"status": "verified"}


@router.post("/telegram/check")
async def check_telegram_login(data: CheckLoginRequest, db: AsyncSession = Depends(get_db)):
    """Step 3: Website polls this endpoint. When bot has verified, return JWT."""
    entry = _pending_tokens.get(data.token)
    if not entry:
        raise HTTPException(404, "Token not found")
    if entry["expires"] < datetime.now(timezone.utc):
        _pending_tokens.pop(data.token, None)
        raise HTTPException(410, "Token expired")
    if entry["state"] != "verified":
        raise HTTPException(202, "Pending — please click the Telegram link")

    # Verified! Find or create user by telegram_id
    tid = entry["telegram_id"]
    result = await db.execute(select(User).where(User.telegram_id == tid))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            username=f"tg_{tid}",
            telegram_id=tid,
            password_hash="telegram_only",
            role="user",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        # Create telegram session
        db.add(TelegramSession(user_id=user.id, chat_id=tid, state="idle", data={}))
        await db.commit()
    if user.is_banned:
        raise HTTPException(403, "Account banned")
    if user.role == "admin":
        raise HTTPException(403, "Admin must login via email+password")

    # Consume token
    _pending_tokens.pop(data.token, None)

    return LoginResponse(
        access_token=create_access_token(user.id, user.role),
        user_id=str(user.id),
        role=user.role,
    )


# Legacy: manual code entry (for fallback)
@router.post("/telegram", response_model=LoginResponse)
async def telegram_login(data: TelegramLoginRequest, db: AsyncSession = Depends(get_db)):
    """Fallback: login via token string (same as check but returns JWT directly)."""
    token = data.code.strip()
    if not token or len(token) < 16:
        raise HTTPException(400, "Invalid token")

    entry = _pending_tokens.get(token)
    if not entry:
        # Try DB login_code (old flow)
        result = await db.execute(
            select(TelegramSession).where(TelegramSession.login_code == token)
        )
        ts = result.scalar_one_or_none()
        if not ts:
            raise HTTPException(401, "Invalid or expired token")
        if ts.login_code_expires and ts.login_code_expires < datetime.now(timezone.utc):
            raise HTTPException(401, "Token expired")
        user_result = await db.execute(select(User).where(User.id == ts.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(404, "User not found")
        if user.is_banned:
            raise HTTPException(403, "Account banned")
        if user.role == "admin":
            raise HTTPException(403, "Admin must login via email+password")
        ts.login_code = None
        ts.login_code_expires = None
        await db.commit()
        return LoginResponse(
            access_token=create_access_token(user.id, user.role),
            user_id=str(user.id),
            role=user.role,
        )

    if entry["expires"] < datetime.now(timezone.utc):
        _pending_tokens.pop(token, None)
        raise HTTPException(401, "Token expired")
    if entry["state"] != "verified":
        raise HTTPException(202, "Pending")

    tid = entry["telegram_id"]
    result = await db.execute(select(User).where(User.telegram_id == tid))
    user = result.scalar_one_or_none()
    if not user:
        user = User(username=f"tg_{tid}", telegram_id=tid, password_hash="telegram_only", role="user")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        db.add(TelegramSession(user_id=user.id, chat_id=tid, state="idle", data={}))
        await db.commit()
    if user.is_banned:
        raise HTTPException(403, "Account banned")
    if user.role == "admin":
        raise HTTPException(403, "Admin must login via email+password")

    _pending_tokens.pop(token, None)
    return LoginResponse(
        access_token=create_access_token(user.id, user.role),
        user_id=str(user.id),
        role=user.role,
    )


# ── Admin 2FA ──
@router.post("/admin/login")
async def admin_login_step1(data: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email, User.role == "admin"))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if user.is_banned:
        raise HTTPException(403, "Account banned")

    code = f"{secrets.randbelow(900000) + 100000}"
    _admin_codes[data.email] = {
        "code": code,
        "expires": datetime.now(timezone.utc) + timedelta(minutes=5),
        "user_id": str(user.id),
    }

    # Send code via email (primary)
    from app.services.email_service import send_admin_code
    sent = await send_admin_code(data.email, code)

    # Also try Telegram if admin has telegram_id
    tg_sent = False
    if user.telegram_id:
        try:
            bot_token = settings.TELEGRAM_BOT_TOKEN
            if bot_token:
                async with async_session() as s:
                    ts = (await s.execute(
                        select(TelegramSession).where(TelegramSession.user_id == user.id)
                    )).scalar_one_or_none()
                    if ts:
                        import aiohttp
                        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                        async with aiohttp.ClientSession() as session:
                            async with session.post(url, json={
                                "chat_id": ts.chat_id,
                                "text": f"🔐 Admin login code: {code}\n⏰ Expires in 5 minutes",
                            }) as r:
                                tg_sent = r.status == 200
        except Exception as e:
            print(f"[admin-login] Telegram send failed: {e}")

    if not sent and not tg_sent:
        raise HTTPException(500, "Failed to send code. Check SMTP config.")

    channel = "email" if sent else "telegram"
    return {"status": "code_sent", "message": f"Code sent via {channel}"}


@router.post("/admin/verify", response_model=LoginResponse)
async def admin_login_step2(data: AdminVerifyRequest, db: AsyncSession = Depends(get_db)):
    entry = _admin_codes.get(data.email)
    if not entry:
        raise HTTPException(401, "No code requested")
    if entry["expires"] < datetime.now(timezone.utc):
        _admin_codes.pop(data.email, None)
        raise HTTPException(401, "Code expired")
    if entry["code"] != data.code.strip():
        raise HTTPException(401, "Invalid code")

    result = await db.execute(select(User).where(User.email == data.email, User.role == "admin"))
    user = result.scalar_one_or_none()
    if not user or user.is_banned:
        raise HTTPException(403, "Account unavailable")

    _admin_codes.pop(data.email, None)
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return LoginResponse(
        access_token=create_access_token(user.id, user.role),
        user_id=str(user.id),
        role="admin",
    )


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
