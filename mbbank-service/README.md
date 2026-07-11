# MBBank Service

NodeJS service for integrating MBBank API with NRO Server web application.

## Setup

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your MBBank credentials
   ```

3. **Start service**
   ```bash
   # Development mode with auto-reload
   npm run dev
   
   # Production mode
   npm start
   ```

## API Endpoints

All endpoints require `X-API-Key` header for authentication.

### Health Check
```
GET /health
```

### Login
```
POST /api/login
Headers: X-API-Key: your_api_key
```

### Get Balance
```
GET /api/balance
Headers: X-API-Key: your_api_key
```

### Get Transactions
```
POST /api/transactions
Headers: X-API-Key: your_api_key
Body: {
  "days": 2,  // optional, default 2
  "fromDate": "2024-01-01",  // optional
  "toDate": "2024-01-31"  // optional
}
```

### Check Deposits
```
POST /api/check-deposits
Headers: X-API-Key: your_api_key
Body: {
  "days": 2,  // optional, default 2
  "pattern": "naptien"  // optional, default "naptien"
}
```

## Running as Windows Service

Use `pm2` or `node-windows` to run as Windows service:

```bash
npm install -g pm2
pm2 start mbbank-service.js --name mbbank
pm2 save
pm2 startup
```
