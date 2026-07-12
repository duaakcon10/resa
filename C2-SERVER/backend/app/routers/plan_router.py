from fastapi import APIRouter, Depends
from uuid import UUID
from typing import List
from app.auth import get_current_user
from app.models.all_models import User, Plan
from app.database import async_session
from sqlalchemy import select

router = APIRouter(prefix="/api/plans", tags=["plans"])

@router.get("/")
async def list_plans(current_user: User = Depends(get_current_user)):
    async with async_session() as s:
        r = await s.execute(select(Plan).where(Plan.is_active == True))
        plans = r.scalars().all()
        return [{
            "id": str(p.id), "name": p.name, "slug": p.slug,
            "description": p.description,
            "max_bots": p.max_bots, "max_concurrent": p.max_concurrent,
            "max_attack_secs": p.max_attack_secs, "cooldown_secs": p.cooldown_secs,
            "max_pps_per_bot": p.max_pps_per_bot, "allowed_methods": p.allowed_methods,
            "price_monthly": float(p.price_usd), "price_vnd": p.price_vnd,
            "is_active": p.is_active,
        } for p in plans]