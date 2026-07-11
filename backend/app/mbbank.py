# ============================================================
# MBBANK PAYMENT — Persistent Session, Minimal Re-login
# ============================================================
# Based on: thedtvn/MBBank (Python) & CookieGMVN/MBBank (Node.js)
# Key: deviceId cố định, session refresh tự động, Redis cache
# ============================================================

import json, uuid, time, asyncio, aiohttp
from typing import Optional, Dict, Any
from app.config import settings
from app.database import get_redis

MB_API = {
    "login":    "https://online.mbbank.com.vn/api/retail_web/internetbanking/doLogin",
    "captcha":  "https://online.mbbank.com.vn/api/retail-web-internetbankingms/getCaptchaImage",
    "balance":  "https://online.mbbank.com.vn/api/retail_web/internetbanking/getBalance",
    "accounts": "https://online.mbbank.com.vn/api/retail_web/internetbanking/getAccountList",
    "history":  "https://online.mbbank.com.vn/api/retail_web/internetbanking/getTransactionHistory",
    "refresh":  "https://online.mbbank.com.vn/api/retail_web/internetbanking/refreshSession",
}

class MBSessionManager:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.device_id: Optional[str] = None
        self.session_id: Optional[str] = None
        self.token: Optional[str] = None
        self.cookie: Optional[str] = None
        self.account_no: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_login = 0
        self._lock = asyncio.Lock()

    @property
    def redis_key(self) -> str: return f"mbank:session:{self.username}"
    @property
    def device_key(self) -> str: return f"mbank:device:{self.username}"

    async def load_session(self) -> bool:
        redis = await get_redis()
        try:
            data = await redis.get(self.redis_key)
            if data:
                s = json.loads(data)
                self.session_id = s.get("session_id")
                self.token = s.get("token")
                self.cookie = s.get("cookie")
                self.account_no = s.get("account_no")
                self.device_id = s.get("device_id")
                self._last_login = s.get("last_login", 0)
                return True
        except: pass
        return False

    async def save_session(self):
        redis = await get_redis()
        data = {
            "session_id": self.session_id, "token": self.token,
            "cookie": self.cookie, "account_no": self.account_no,
            "device_id": self.device_id, "last_login": int(time.time()),
        }
        await redis.set(self.redis_key, json.dumps(data), ex=86400)

    async def load_device_id(self) -> str:
        redis = await get_redis()
        did = await redis.get(self.device_key)
        if not did:
            did = f"{uuid.uuid4().hex[:8]}-mbib-0000-0000-{time.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6]}"
            await redis.set(self.device_key, did)
        self.device_id = did
        return did

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "vi-VN,vi;q=0.9",
                "Content-Type": "application/json",
                "Origin": "https://online.mbbank.com.vn",
                "Referer": "https://online.mbbank.com.vn/",
            }
            if self.cookie: headers["Cookie"] = self.cookie
            if self.token: headers["Authorization"] = f"Basic {self.token}"
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def _api_post(self, url: str, data: dict) -> dict:
        session = await self._get_session()
        async with session.post(url, json=data) as resp:
            raw_cookies = resp.headers.getall("Set-Cookie")
            if raw_cookies:
                new_cookies = []
                for c in raw_cookies: new_cookies.append(c.split(";")[0])
                if new_cookies: self.cookie = "; ".join(new_cookies); await self.save_session()
            return await resp.json()

    async def _api_get(self, url: str, params: dict = None) -> dict:
        session = await self._get_session()
        async with session.get(url, params=params) as resp:
            return await resp.json()

    async def _validate_session(self) -> bool:
        try:
            result = await self._api_get(MB_API["balance"])
            if result.get("result") and result["result"].get("acct_list"): return True
        except: pass
        try:
            result = await self._api_post(MB_API["refresh"], {
                "sessionId": self.session_id, "deviceId": self.device_id,
            })
            if result.get("result") and result["result"].get("ok") == 1:
                self.session_id = result["result"].get("sessionId", "")
                self.token = result["result"].get("token", "")
                await self.save_session(); return True
        except: pass
        return False

    async def login(self, force: bool = False) -> bool:
        async with self._lock:
            if not force and await self.load_session():
                if await self._validate_session(): return True
            await self.load_device_id()

            # Get captcha
            session = await self._get_session()
            async with session.get(MB_API["captcha"]) as resp:
                captcha_data = await resp.json()
                captcha_data = captcha_data.get("result", {})

            # Solve captcha via OCR or Telegram
            captcha_text = await self._solve_captcha(captcha_data)
            if not captcha_text: raise Exception("Failed to solve captcha")

            login_data = {
                "username": self.username, "password": self.password,
                "captcha": captcha_text, "deviceId": self.device_id,
                "sessionId": captcha_data.get("sessionId", ""),
                "refNo": captcha_data.get("refNo", ""),
            }
            result = await self._api_post(MB_API["login"], login_data)
            if result.get("result") and result["result"].get("ok") == 1:
                self.session_id = result["result"].get("sessionId", "")
                self.token = result["result"].get("token", "")
                await self._fetch_accounts()
                self._last_login = int(time.time()); await self.save_session()
                return True
            raise Exception(f"MB Login failed: {result.get('result', {}).get('message', 'Unknown')}")

    async def _solve_captcha(self, captcha_data: dict) -> Optional[str]:
        try:
            import base64
            img_data = captcha_data.get("image", "")
            if not img_data: return None
            try:
                from PIL import Image
                import pytesseract
                from io import BytesIO
                img = Image.open(BytesIO(base64.b64decode(img_data)))
                text = pytesseract.image_to_string(img, config="--psm 7 -c tessedit_char_whitelist=0123456789")
                text = "".join(c for c in text if c.isdigit())
                if len(text) >= 4: return text[:6]
            except ImportError: pass
            if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_ADMIN_CHAT_ID:
                from telegram import Bot
                bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
                await bot.send_photo(chat_id=settings.TELEGRAM_ADMIN_CHAT_ID, photo=base64.b64decode(img_data), caption="🔐 MB Captcha — Reply with the code")
                for _ in range(30):
                    await asyncio.sleep(1)
                    redis = await get_redis()
                    code = await redis.get("mbank:captcha:answer")
                    if code: await redis.delete("mbank:captcha:answer"); return code
            return None
        except Exception as e:
            print(f"[MB] Captcha error: {e}"); return None

    async def _fetch_accounts(self):
        result = await self._api_get(MB_API["accounts"])
        if result.get("result") and result["result"].get("acct_list"):
            self.account_no = result["result"]["acct_list"][0].get("acctNo", "")
            await self.save_session()

    async def get_balance(self) -> Dict[str, Any]:
        if not await self.login(): raise Exception("MB auth failed")
        result = await self._api_get(MB_API["balance"])
        return result.get("result", {})

    async def get_transactions(self, from_date: str, to_date: str, limit: int = 50) -> list:
        if not await self.login(): raise Exception("MB auth failed")
        if not self.account_no: raise Exception("No account")
        result = await self._api_post(MB_API["history"], {
            "accountNo": self.account_no, "fromDate": from_date, "toDate": to_date,
            "sessionId": self.session_id, "deviceId": self.device_id,
        })
        return result.get("result", {}).get("transactionList", [])

    async def scan_for_payments(self, amount: int, description: str = None, minutes_back: int = 30) -> Optional[dict]:
        now = time.strftime("%d/%m/%Y")
        transactions = await self.get_transactions(now, now, limit=100)
        for tx in transactions:
            tx_amount = tx.get("creditAmount", 0) or tx.get("amount", 0)
            tx_amount = abs(int(float(tx_amount)))
            if tx_amount == amount:
                if description and description.lower() not in str(tx.get("description", "")).lower(): continue
                return {
                    "tx_id": tx.get("refNo", tx.get("transactionId", "")),
                    "amount": tx_amount, "description": tx.get("description", ""),
                    "date": tx.get("transactionDate", ""),
                    "sender_name": tx.get("senderName", ""),
                    "sender_account": tx.get("senderAccount", ""),
                }
        return None

    async def close(self):
        if self._session and not self._session.closed: await self._session.close(); self._session = None

_mb_instance: Optional[MBSessionManager] = None

async def get_mb() -> Optional[MBSessionManager]:
    global _mb_instance
    if _mb_instance is None and settings.MB_USERNAME and settings.MB_PASSWORD:
        _mb_instance = MBSessionManager(settings.MB_USERNAME, settings.MB_PASSWORD)
        try:
            if await _mb_instance.login(): print("[MB] Login successful")
            else: print("[MB] Login failed")
        except Exception as e: print(f"[MB] Login error: {e}")
    return _mb_instance

async def mb_payment_scanner():
    from app.database import async_session
    from app.models.all_models import Payment, UserSubscription, Plan, User
    from sqlalchemy import select
    from datetime import timedelta, datetime, timezone
    while True:
        await asyncio.sleep(30)
        mb = await get_mb()
        if not mb: continue
        try:
            async with async_session() as s:
                r = await s.execute(select(Payment).where(Payment.status == "pending", Payment.method == "mbank").order_by(Payment.created_at.asc()))
                pending = r.scalars().all()
            if not pending: continue
            for payment in pending:
                matched = await mb.scan_for_payments(amount=payment.amount_vnd, minutes_back=60)
                if matched:
                    async with async_session() as s:
                        r = await s.execute(select(Payment).where(Payment.id == payment.id))
                        p = r.scalar_one_or_none()
                        if p and p.status == "pending":
                            p.status = "completed"
                            p.completed_at = datetime.now(timezone.utc)
                            p.tx_ref = matched["tx_id"]
                            p.meta = {**p.meta, "matched_tx": matched}
                            r2 = await s.execute(select(Plan).where(Plan.price_vnd == payment.amount_vnd))
                            plan = r2.scalar_one_or_none()
                            if plan:
                                s.add(UserSubscription(user_id=payment.user_id, plan_id=plan.id, status="active", expires_at=datetime.now(timezone.utc) + timedelta(days=30), payment_id=payment.tx_ref))
                            await s.commit()
                            if settings.TELEGRAM_BOT_TOKEN:
                                try:
                                    from telegram import Bot
                                    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
                                    r3 = await s.execute(select(User).where(User.id == payment.user_id))
                                    user = r3.scalar_one_or_none()
                                    if user and user.telegram_id:
                                        await bot.send_message(chat_id=user.telegram_id, text=f"✅ Thanh toán {payment.amount_vnd:,}đ đã được xác nhận!\nPlan của bạn đã được kích hoạt.")
                                except: pass
                        print(f"[MB] Payment confirmed: {payment.amount_vnd:,}đ via {matched['tx_id']}")
        except Exception as e: print(f"[MB] Scanner error: {e}")

async def handle_mb_captcha_reply(telegram_id: int, text: str):
    if text.isdigit() and len(text) >= 4:
        redis = await get_redis()
        await redis.set("mbank:captcha:answer", text, ex=120)
        return True
    return False