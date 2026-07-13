# ============================================================
# MB Bank payment via mbbank-service (Node @doa69/mbbank)
# + VietQR image URL for easy bank transfer
# ============================================================
import json
import time
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List
from urllib.parse import quote
from app.config import settings
from app.database import get_redis

# Napas bank BIN for MB Bank
MB_BANK_BIN = "970422"


def build_vietqr_url(
    account_no: str,
    amount: int,
    description: str,
    account_name: str = "",
    template: str = "compact2",
) -> str:
    """
    VietQR image URL (img.vietqr.io) — auto-fills STK, amount, content when scanned.
    Docs: https://www.vietqr.io/danh-sach-api/link-tao-ma-nhanh
    """
    acc = quote(str(account_no).strip(), safe="")
    add = quote((account_name or "C2 Payment").strip()[:50], safe="")
    info = quote((description or "").strip()[:25], safe="")
    return (
        f"https://img.vietqr.io/image/{MB_BANK_BIN}-{acc}-{template}.png"
        f"?amount={int(amount)}&addInfo={info}&accountName={add}"
    )


class MBServiceClient:
    """HTTP client for mbbank-service (Node)."""

    def __init__(self):
        raw = (settings.MB_SERVICE_URL or "http://127.0.0.1:3000").rstrip("/")
        # 0.0.0.0 is listen-only; never use as client host
        if "0.0.0.0" in raw:
            raw = raw.replace("0.0.0.0", "127.0.0.1")
        self.base = raw
        self.api_key = settings.MB_SERVICE_API_KEY or "c2-mb-internal-key"
        self.account_no = settings.MB_ACCOUNT_NUMBER or ""
        self.account_name = settings.MB_ACCOUNT_NAME or ""
        self._session: Optional[aiohttp.ClientSession] = None
        # Candidate bases if primary DNS fails (Docker / host mix)
        self._bases = [self.base]
        for alt in (
            "http://mbbank:3000",
            "http://c2-mbbank:3000",
            "http://host.docker.internal:3000",
            "http://127.0.0.1:3000",
        ):
            if alt not in self._bases:
                self._bases.append(alt)

    def _headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _session_get(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers=self._headers(),
            )
        return self._session

    async def health(self) -> bool:
        """Probe /health; on DNS failure try alternate bases and stick to first that works."""
        s = await self._session_get()
        last_err = None
        for base in list(self._bases):
            try:
                async with s.get(f"{base}/health") as r:
                    if r.status != 200:
                        continue
                    data = await r.json()
                    if data.get("success"):
                        if base != self.base:
                            print(f"[MB-Service] using {base} (was {self.base})")
                            self.base = base
                        return True
            except Exception as e:
                last_err = e
                continue
        print(f"[MB-Service] health error: {last_err}")
        return False

    async def login(self) -> bool:
        try:
            s = await self._session_get()
            async with s.post(f"{self.base}/api/login") as r:
                data = await r.json()
                ok = bool(data.get("success"))
                print(f"[MB-Service] login: {data.get('message', ok)}")
                return ok
        except Exception as e:
            print(f"[MB-Service] login error: {e}")
            return False

    async def get_balance(self) -> Optional[dict]:
        try:
            s = await self._session_get()
            async with s.get(f"{self.base}/api/balance") as r:
                data = await r.json()
                if data.get("success"):
                    return data.get("data")
        except Exception as e:
            print(f"[MB-Service] balance error: {e}")
        return None

    async def get_transactions(self, days: int = 2) -> List[dict]:
        try:
            s = await self._session_get()
            async with s.post(
                f"{self.base}/api/transactions",
                json={"days": days},
            ) as r:
                data = await r.json()
                if data.get("success"):
                    d = data.get("data") or {}
                    return list(d.get("transactions") or [])
        except Exception as e:
            print(f"[MB-Service] transactions error: {e}")
        return []

    async def check_deposits(self, pattern: str, days: int = 2) -> List[dict]:
        try:
            s = await self._session_get()
            async with s.post(
                f"{self.base}/api/check-deposits",
                json={"days": days, "pattern": pattern},
            ) as r:
                data = await r.json()
                if data.get("success"):
                    d = data.get("data") or {}
                    return list(d.get("deposits") or [])
        except Exception as e:
            print(f"[MB-Service] check-deposits error: {e}")
        return []

    async def find_payment(self, amount: int, description: str, days: int = 2) -> Optional[dict]:
        """Match credit by amount + transfer content (tx_ref)."""
        desc = (description or "").strip().lower()
        # Prefer check-deposits with pattern = tx_ref
        deposits = await self.check_deposits(pattern=description or "", days=days)
        for tx in deposits:
            amt = int(float(tx.get("amount") or 0))
            if amt == int(amount):
                return {
                    "tx_id": tx.get("refNo") or tx.get("transactionDate") or "",
                    "amount": amt,
                    "description": tx.get("description") or "",
                    "date": tx.get("transactionDate") or "",
                    "sender_name": tx.get("benAccountName") or "",
                }

        # Fallback: scan all transactions
        txs = await self.get_transactions(days=days)
        for tx in txs:
            credit = tx.get("creditAmount") or tx.get("amount") or 0
            try:
                amt = abs(int(float(credit)))
            except (TypeError, ValueError):
                continue
            if amt != int(amount):
                continue
            tdesc = str(tx.get("description") or "").lower()
            if desc and desc not in tdesc:
                continue
            return {
                "tx_id": tx.get("refNo") or tx.get("transactionId") or "",
                "amount": amt,
                "description": tx.get("description") or "",
                "date": tx.get("transactionDate") or "",
                "sender_name": tx.get("senderName") or tx.get("benAccountName") or "",
            }
        return None

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None


_mb_client: Optional[MBServiceClient] = None


async def get_mb() -> Optional[MBServiceClient]:
    """Return client if mbbank-service is configured and reachable."""
    global _mb_client
    if not settings.MB_SERVICE_URL and not settings.MB_USERNAME:
        return None
    if _mb_client is None:
        _mb_client = MBServiceClient()
        # Warm login (non-fatal)
        try:
            await _mb_client.login()
        except Exception as e:
            print(f"[MB-Service] warm login: {e}")
    return _mb_client


def payment_qr_payload(
    amount: int,
    tx_ref: str,
    account_no: Optional[str] = None,
    account_name: Optional[str] = None,
) -> dict:
    acc = account_no or settings.MB_ACCOUNT_NUMBER or ""
    name = account_name or settings.MB_ACCOUNT_NAME or "C2 Payment"
    qr = build_vietqr_url(acc, amount, tx_ref, name) if acc else ""
    return {
        "status": "pending",
        "tx_ref": tx_ref,
        "amount": amount,
        "bank_account": acc or "Chua cau hinh MB_ACCOUNT_NUMBER",
        "bank_name": "MB Bank (Ngan hang Quan doi)",
        "bank_bin": MB_BANK_BIN,
        "account_name": name,
        "description": tx_ref,
        "qr_url": qr,
        "qr_image": qr,
        "message": f"Quet VietQR hoac CK {amount:,}d noi dung: {tx_ref}",
    }


async def mb_payment_scanner():
    """Background task: poll mbbank-service for pending payments."""
    from app.database import async_session
    from app.models.all_models import Payment, UserSubscription, Plan, User
    from sqlalchemy import select
    from datetime import timedelta, datetime, timezone

    print("[MB] Payment scanner started (mbbank-service)")
    while True:
        await asyncio.sleep(30)
        try:
            mb = await get_mb()
            if not mb:
                continue
            async with async_session() as s:
                r = await s.execute(
                    select(Payment).where(
                        Payment.status == "pending",
                        Payment.method == "mbank",
                    ).order_by(Payment.created_at.asc())
                )
                pending = list(r.scalars().all())

            if not pending:
                continue

            for payment in pending:
                # Prefer matching by tx_ref in transfer content
                matched = await mb.find_payment(
                    amount=int(payment.amount_vnd),
                    description=payment.tx_ref or "",
                    days=3,
                )
                if not matched:
                    continue

                async with async_session() as s:
                    r = await s.execute(select(Payment).where(Payment.id == payment.id))
                    p = r.scalar_one_or_none()
                    if not p or p.status != "pending":
                        continue

                    # Keep original tx_ref for user; store bank ref in meta
                    meta = dict(p.meta or {})
                    meta["matched_tx"] = matched
                    meta["bank_ref"] = matched.get("tx_id")
                    p.status = "completed"
                    p.completed_at = datetime.now(timezone.utc)
                    p.meta = meta

                    plan_id = meta.get("plan_id")
                    plan = None
                    if plan_id:
                        try:
                            import uuid as _uuid
                            r2 = await s.execute(select(Plan).where(Plan.id == _uuid.UUID(str(plan_id))))
                            plan = r2.scalar_one_or_none()
                        except Exception:
                            plan = None
                    if not plan:
                        r2 = await s.execute(select(Plan).where(Plan.price_vnd == payment.amount_vnd))
                        plan = r2.scalar_one_or_none()

                    if plan:
                        s.add(UserSubscription(
                            user_id=payment.user_id,
                            plan_id=plan.id,
                            status="active",
                            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                            payment_id=payment.tx_ref,
                        ))
                    await s.commit()

                    if settings.TELEGRAM_BOT_TOKEN:
                        try:
                            from telegram import Bot
                            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
                            r3 = await s.execute(select(User).where(User.id == payment.user_id))
                            user = r3.scalar_one_or_none()
                            if user and user.telegram_id:
                                await bot.send_message(
                                    chat_id=user.telegram_id,
                                    text=(
                                        f"✅ Thanh toán {payment.amount_vnd:,}đ đã xác nhận!\n"
                                        f"Nội dung: `{payment.tx_ref}`\n"
                                        f"Plan đã kích hoạt."
                                    ),
                                    parse_mode="Markdown",
                                )
                        except Exception:
                            pass

                print(f"[MB] Payment OK: {payment.amount_vnd:,}đ ref={payment.tx_ref}")
        except Exception as e:
            print(f"[MB] Scanner error: {e}")
