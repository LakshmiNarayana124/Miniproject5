# IntelliWatch — Deployment Guide

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Vercel     │────▶│   Railway    │────▶│    Neon      │
│  (Frontend)  │ API │  (Backend)   │ DB  │  (Postgres)  │
│  React+Vite  │     │  FastAPI     │     │  Serverless  │
└──────────────┘     └──────────────┘     └──────────────┘
```

---

## 1. Neon (Database)

### Create
1. Sign up at [neon.tech](https://neon.tech) — free tier: 0.5 GB storage
2. Create a new project → copy the **Connection string**:
   ```
   postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
   ```

### Migrate from SQLite to Neon
```bash
set NEON_DIRECT_URL=postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
python migrate_sqlite_to_neon.py
```

The script reads all tables from `Backend/database/intelliwatch.db`, converts SQLite DDL to Postgres DDL, copies all records, and verifies row counts.

---

## 2. Railway (Backend)

### Setup
1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
2. Select `LakshmiNarayana124/Miniproject5`
3. Railway will detect `railway.toml` at the root automatically
4. Set **Root Directory** to `Backend` in the service settings
5. Add environment variables:

| Variable | Value |
|---|---|
| `INTELLIWATCH_SECRET_KEY` | 64-char hex string (`openssl rand -hex 32`) |
| `DATABASE_URL` | Neon connection string |
| `INTELLIWATCH_CORS_ORIGINS` | Your Vercel frontend URL |
| `FIREBASE_PROJECT_ID` | From Firebase Console (for Google/Phone login) |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Optional — enables phone OTP verification |

6. Deploy — Railway builds using `Backend/nixpacks.toml` (Python 3.11, pip install)
7. Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
8. Health check: `GET /auth/registration-status`

### After deploy
Your backend URL will be `https://intelliwatch-backend.up.railway.app` (or similar)

---

## 3. Vercel (Frontend)

### Deploy
1. Go to [vercel.com](https://vercel.com) → New Project → Import `Miniproject5`
2. Vercel reads `vercel.json` from the root automatically
3. Set environment variables:

| Variable | Value |
|---|---|
| `VITE_API_URL` | Your Railway backend URL |
| `VITE_FIREBASE_API_KEY` | From Firebase Console |
| `VITE_FIREBASE_AUTH_DOMAIN` | From Firebase Console |
| `VITE_FIREBASE_PROJECT_ID` | From Firebase Console |
| `VITE_FIREBASE_STORAGE_BUCKET` | From Firebase Console |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | From Firebase Console |
| `VITE_FIREBASE_APP_ID` | From Firebase Console |

4. Deploy

### After deploy
- Your frontend URL: `https://intelliwatch.vercel.app` (or your chosen name)
- Go back to Railway → update `INTELLIWATCH_CORS_ORIGINS` to this URL
- Go back to Firebase Console → Authentication → Authorized domains → add this URL

---

## 4. Firebase Console Setup

1. Firebase Console → Authentication → Sign-in method
2. Enable **Google**
3. Enable **Phone** (requires Blaze plan for SMS)
4. Add authorized domains: your Vercel URL

---

## 5. Post-Deploy Checklist

- [ ] Railway service is running — health check returns `{"registration_enabled": true}`
- [ ] `DATABASE_URL` is set in Railway → tables auto-created on first request
- [ ] `INTELLIWATCH_CORS_ORIGINS` in Railway matches Vercel URL exactly
- [ ] Firebase authorized domains includes Vercel URL
- [ ] `VITE_API_URL` in Vercel points to Railway URL (no trailing slash)
- [ ] PWA installable — visit frontend on Android Chrome → "Add to Home Screen"

---

## Local Development

### Backend
```bash
cd Backend
pip install -r requirements.txt
set INTELLIWATCH_SECRET_KEY=<64-char-hex>
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm install
# create .env.local:
#   VITE_API_URL=http://localhost:8000
npm run dev
```

Open `http://localhost:5173`
