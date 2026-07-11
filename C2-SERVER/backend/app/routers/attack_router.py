from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from app.auth import get_current_user
from app.models.all_models import User
from app.schemas.all_schemas import AttackCreate, AttackOut
from app.services.attack_service import AttackService

router = APIRouter(prefix="/api/attacks", tags=["attacks"])

@router.post("/launch", response_model=AttackOut)
async def launch_attack(data: AttackCreate, current_user: User = Depends(get_current_user)):
    task = await AttackService.launch(current_user, data)
    return AttackOut.model_validate(task)

@router.post("/{task_id}/stop")
async def stop_attack(task_id: UUID, current_user: User = Depends(get_current_user)):
    await AttackService.stop(task_id, current_user.id)
    return {"status": "stopped", "task_id": str(task_id)}

@router.get("/mine")
async def my_attacks(current_user: User = Depends(get_current_user)):
    tasks = await AttackService.get_user_tasks(current_user.id)
    return [AttackOut.model_validate(t) for t in tasks]

@router.get("/active")
async def active_attacks(current_user: User = Depends(get_current_user)):
    if current_user.role == "admin": tasks = await AttackService.get_active_tasks()
    else: tasks = await AttackService.get_active_tasks(user_id=current_user.id)
    return [AttackOut.model_validate(t) for t in tasks]