# MBBank Service
Node service for MB payment scan (package: `mbbank` / CookieGMVN).

## Setup
```bash
npm install
cp .env.example .env
# edit credentials
npm start
```

## API (header `X-API-Key` required except /health)
- `GET /health`
- `POST /api/login`
- `GET /api/balance`
- `POST /api/transactions` body: `{ "days": 2 }`
- `POST /api/check-deposits` body: `{ "days": 2, "pattern": "C2ABC123" }`

## Docker
Built automatically via `deployment/docker-compose.yml` service `mbbank`.
