#!/bin/bash
# ============================================================
# C2 SERVER — 1 LỆNH TỰ ĐỘNG CÀI ĐẶT
# ============================================================
# Usage: curl -sL https://bot.minhvuong.io.vn/deploy.sh -o deploy.sh && bash deploy.sh
#    or: chmod +x deploy.sh && ./deploy.sh
# ============================================================
set -e

# ── Colors ───────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║          🎯 C2 COMMAND CENTER — AUTO DEPLOY          ║"
    echo "║                 v4.0.0 — Ultimate                    ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

info()  { echo -e "${BLUE}[*]${NC} $1"; }
ok()    { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }
ask()   { echo -ne "${CYAN}[?]${NC} $1: "; }

# ── Step 1: System Detection ──────────────────────
detect_system() {
    info "Detecting system resources..."

    TOTAL_CPU=$(nproc 2>/dev/null || echo 2)
    TOTAL_RAM_MB=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}')
    TOTAL_RAM_MB=${TOTAL_RAM_MB:-2048}
    TOTAL_DISK_GB=$(df -BG / 2>/dev/null | awk 'NR==2{print $4}' | tr -d 'G')
    TOTAL_DISK_GB=${TOTAL_DISK_GB:-20}
    OS_NAME=$(grep "^ID=" /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"')
    OS_NAME=${OS_NAME:-linux}
    HAS_DOCKER=$(command -v docker &>/dev/null && echo "yes" || echo "no")
    HAS_COMPOSE=$(docker compose version &>/dev/null && echo "yes" || echo "no")
    HAS_GIT=$(command -v git &>/dev/null && echo "yes" || echo "no")
    HAS_NODE=$(command -v node &>/dev/null && echo "yes" || echo "no")
    HAS_NPM=$(command -v npm &>/dev/null && echo "yes" || echo "no")

    ok "CPU: ${TOTAL_CPU} cores | RAM: ${TOTAL_RAM_MB}MB | Disk: ${TOTAL_DISK_GB}GB"
    ok "OS: ${OS_NAME} | Docker: ${HAS_DOCKER} | Git: ${HAS_GIT} | Node: ${HAS_NODE}"

    # Tính toán phân bổ resource
    if [ "$TOTAL_RAM_MB" -lt 1024 ]; then
        warn "RAM < 1GB — chỉ phân bổ tối thiểu"
        DB_MEM="256m"; REDIS_MEM="128m"; API_MEM="256m"
        DB_SHARED_BUFFERS="128MB"; DB_EFFECTIVE_CACHE="256MB"
    elif [ "$TOTAL_RAM_MB" -lt 4096 ]; then
        DB_MEM="512m"; REDIS_MEM="256m"; API_MEM="512m"
        DB_SHARED_BUFFERS="256MB"; DB_EFFECTIVE_CACHE="512MB"
    else
        DB_MEM="1g"; REDIS_MEM="512m"; API_MEM="1g"
        DB_SHARED_BUFFERS="512MB"; DB_EFFECTIVE_CACHE="1024MB"
    fi

    POSTGRES_CPU=$(( TOTAL_CPU / 4 ))
    [ "$POSTGRES_CPU" -lt 1 ] && POSTGRES_CPU=1
    API_CPU=$(( TOTAL_CPU / 2 ))
    [ "$API_CPU" -lt 1 ] && API_CPU=1

    ok "Auto-allocated: DB=${DB_MEM}/${POSTGRES_CPU}c | Redis=${REDIS_MEM} | API=${API_MEM}/${API_CPU}c"
}

# ── Step 2: Install Dependencies ──────────────────
install_deps() {
    info "Installing dependencies..."

    if [ "$HAS_DOCKER" = "no" ]; then
        warn "Installing Docker..."
        curl -fsSL https://get.docker.com | bash
        systemctl enable docker --now
    fi

    if [ "$HAS_COMPOSE" = "no" ]; then
        warn "Docker Compose plugin not found, using standalone..."
    fi

    if [ "$HAS_NODE" = "no" ] || [ "$HAS_NPM" = "no" ]; then
        warn "Installing Node.js..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y nodejs
    fi

    ok "Dependencies ready"
}

# ── Step 3: Configuration ─────────────────────────
configure() {
    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}           CẤU HÌNH C2 SERVER${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # ── Bắt buộc ──────────────────────────────────
    ask "Domain (VD: bot.minhvuong.io.vn)"; read -r C2_DOMAIN < /dev/tty
    C2_DOMAIN=${C2_DOMAIN:-localhost}

    ask "Dashboard URL (VD: https://bot.minhvuong.io.vn)"; read -r DASHBOARD_URL < /dev/tty
    DASHBOARD_URL=${DASHBOARD_URL:-https://${C2_DOMAIN}}

    # ── Database ──────────────────────────────────
    DB_PASSWORD=$(openssl rand -hex 16 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 32)
    REDIS_PASSWORD=$(openssl rand -hex 12 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 24)
    JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 64)

    ok "Generated: DB password, Redis password, JWT secret"

    # ── Telegram (optional) ───────────────────────
    echo ""
    info "Telegram Bot (optional — gõ ENTER để bỏ qua)"
    ask "Telegram Bot Token (từ @BotFather)"; read -r TELEGRAM_BOT_TOKEN < /dev/tty
    ask "Admin Chat ID (lấy từ @userinfobot)"; read -r TELEGRAM_ADMIN_CHAT_ID < /dev/tty

    # ── Stripe (optional) ─────────────────────────
    echo ""
    info "Stripe Payment (optional — gõ ENTER để bỏ qua)"
    ask "Stripe Secret Key (sk_live_xxx)"; read -r STRIPE_SECRET_KEY < /dev/tty
    ask "Stripe Webhook Secret (whsec_xxx)"; read -r STRIPE_WEBHOOK_SECRET < /dev/tty

    # ── MB Bank (optional) ────────────────────────
    echo ""
    info "MB Bank Auto-Payment (optional — gõ ENTER để bỏ qua)"
    ask "MB Username (số điện thoại)"; read -r MB_USERNAME < /dev/tty
    ask "MB Password"; read -rs MB_PASSWORD < /dev/tty; echo ""

    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ Cấu hình hoàn tất!${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ── Step 4: Generate .env ─────────────────────────
generate_env() {
    info "Generating .env file..."

    cat > deployment/.env << EOF
# ── Database ────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://c2_admin:${DB_PASSWORD}@postgres:5432/c2_db
DB_PASSWORD=${DB_PASSWORD}
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
REDIS_PASSWORD=${REDIS_PASSWORD}

# ── Auth ────────────────────────────────────────
JWT_SECRET=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# ── Server ──────────────────────────────────────
C2_HOST=0.0.0.0
C2_PORT=443
C2_DOMAIN=${C2_DOMAIN}
DASHBOARD_URL=${DASHBOARD_URL}

# ── Telegram ────────────────────────────────────
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_ADMIN_CHAT_ID=${TELEGRAM_ADMIN_CHAT_ID}

# ── Stripe ──────────────────────────────────────
STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}

# ── MB Bank ─────────────────────────────────────
MB_USERNAME=${MB_USERNAME}
MB_PASSWORD=${MB_PASSWORD}

# ── Logging ─────────────────────────────────────
LOG_LEVEL=INFO
EOF

    ok ".env generated"
}

# ── Step 5: Generate docker-compose với resource ──
generate_compose() {
    info "Generating docker-compose with resource limits..."

    cat > deployment/docker-compose.yml << EOF
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: c2_db
      POSTGRES_USER: c2_admin
      POSTGRES_PASSWORD: \${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ../database/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U c2_admin -d c2_db"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: ${DB_MEM}
          cpus: '${POSTGRES_CPU}.0'
    command: >
      -c shared_buffers=${DB_SHARED_BUFFERS}
      -c effective_cache_size=${DB_EFFECTIVE_CACHE}
      -c max_connections=100
      -c random_page_cost=1.1

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --requirepass \${REDIS_PASSWORD} --maxmemory ${REDIS_MEM} --maxmemory-policy allkeys-lru
    ports:
      - "127.0.0.1:6379:6379"
    deploy:
      resources:
        limits:
          memory: ${REDIS_MEM}

  api:
    build: ../backend
    restart: unless-stopped
    volumes:
      - ../frontend/dist:/frontend/dist:ro
    environment:
      DATABASE_URL: postgresql+asyncpg://c2_admin:\${DB_PASSWORD}@postgres:5432/c2_db
      REDIS_URL: redis://:\${REDIS_PASSWORD}@redis:6379
      JWT_SECRET: \${JWT_SECRET}
      C2_HOST: 0.0.0.0
      C2_PORT: 443
      C2_DOMAIN: \${C2_DOMAIN}
      DASHBOARD_URL: \${DASHBOARD_URL}
      TELEGRAM_BOT_TOKEN: \${TELEGRAM_BOT_TOKEN}
      TELEGRAM_ADMIN_CHAT_ID: \${TELEGRAM_ADMIN_CHAT_ID}
      STRIPE_SECRET_KEY: \${STRIPE_SECRET_KEY}
      STRIPE_WEBHOOK_SECRET: \${STRIPE_WEBHOOK_SECRET}
      MB_USERNAME: \${MB_USERNAME}
      MB_PASSWORD: \${MB_PASSWORD}
      LOG_LEVEL: \${LOG_LEVEL:-INFO}
    ports:
      - "80:443"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    deploy:
      resources:
        limits:
          memory: ${API_MEM}
          cpus: '${API_CPU}.0'

volumes:
  pgdata:
EOF

    ok "docker-compose.yml generated with auto resource allocation"
}

# ── Step 6: Build & Deploy ────────────────────────
build_and_deploy() {
    info "Building frontend..."
    ( cd frontend && npm install --silent && npm run build ) || { err "Frontend build failed"; exit 1; }
    ok "Frontend built → frontend/dist/"

    info "Building Docker images & starting..."
    docker compose -f deployment/docker-compose.yml build || { err "Docker build failed"; exit 1; }
    docker compose -f deployment/docker-compose.yml up -d || { err "Docker up failed"; exit 1; }

    ok "Containers started"
}

# ── Step 7: Verify ───────────────────────────────
verify() {
    info "Verifying deployment..."
    sleep 5

    # Check containers
    RUNNING=$(docker compose -f deployment/docker-compose.yml ps --format json 2>/dev/null | grep '"Health":"healthy"' | wc -l)
    TOTAL=$(docker compose -f deployment/docker-compose.yml ps --format json 2>/dev/null | wc -l)

    info "Containers: ${RUNNING}/${TOTAL} running"

    # Check API
    if curl -s http://localhost/health 2>/dev/null | grep -q "ok"; then
        ok "API health check: PASS"
    else
        warn "API health check: waiting... (có thể mất 10-30s để khởi động)"
    fi

    # Check DB
    if docker compose -f deployment/docker-compose.yml exec -T postgres pg_isready -U c2_admin -d c2_db 2>/dev/null; then
        ok "Database: PASS"
    fi
}

# ── Step 8: Summary ──────────────────────────────
summary() {
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║              🎉 DEPLOYMENT COMPLETE!                 ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${GREEN}🌐 Web Dashboard:${NC}  ${DASHBOARD_URL}"
    echo -e "  ${GREEN}🔌 API Endpoint:${NC}   https://${C2_DOMAIN}"
    echo -e "  ${GREEN}🤖 Bot WebSocket:${NC}  wss://${C2_DOMAIN}/ws/bot/"
    echo -e "  ${GREEN}📱 Telegram Bot:${NC}   ${TELEGRAM_BOT_TOKEN:+Enabled}${TELEGRAM_BOT_TOKEN:-Disabled}"
    echo -e "  ${GREEN}💳 Stripe:${NC}         ${STRIPE_SECRET_KEY:+Enabled}${STRIPE_SECRET_KEY:-Disabled}"
    echo -e "  ${GREEN}🏦 MB Bank:${NC}        ${MB_USERNAME:+Enabled}${MB_USERNAME:-Disabled}"
    echo ""
    echo -e "  ${CYAN}👤 Admin Login:${NC}    admin / admin123"
    echo -e "  ${YELLOW}⚠️  ĐỔI MẬT KHẨU ADMIN NGAY SAU KHI ĐĂNG NHẬP!${NC}"
    echo ""
    echo -e "  ${CYAN}📋 Các lệnh hữu ích:${NC}"
    echo -e "  docker compose -f deployment/docker-compose.yml logs -f api"
    echo -e "  docker compose -f deployment/docker-compose.yml restart"
    echo -e "  docker compose -f deployment/docker-compose.yml down"
    echo ""
    echo -e "  ${CYAN}🤖 Deploy bot lên VPS:${NC}"
    echo -e "  curl -sL https://raw.githubusercontent.com/YOUR_ORG/bot/main/install.sh | bash -s wss://${C2_DOMAIN}/ws/bot/"
    echo ""
}

# ═══════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════

# Check root
if [ "$EUID" -ne 0 ] && [ "$(id -u)" -ne 0 ]; then
    warn "Không chạy với root. Một số bước có thể cần sudo."
    warn "Chạy: sudo bash $0"
    echo ""
fi

banner
detect_system
install_deps
configure
generate_env
generate_compose
build_and_deploy
verify
summary

# ── Save config for later ────────────────────────
echo ""
info "Đã lưu cấu hình vào deployment/.env"
info "Để deploy lại: docker compose -f deployment/docker-compose.yml up -d"
info "Để xóa toàn bộ: docker compose -f deployment/docker-compose.yml down -v"