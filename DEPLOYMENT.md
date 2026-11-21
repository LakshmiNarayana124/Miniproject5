# IntelliWatch — Deployment Guide

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Vercel     │────▶│    Render    │────▶│    Neon      │
│  (Frontend)  │ API │  (Backend)   │ DB  │  (Postgres)  │
│  React+Vite  │     │  FastAPI     │     │  Serverless  │
└──────────────┘     └──────────────┘     └──────────────┘
```

**Cost: $0/month** — Vercel Hobby + Render Free + Neon Free + Firebase Spark

> Render free tier sleeps after 15 min idle. First request after sleep takes ~30 s.

---

## 1. Neon (Database)

### Create
1. Sign up at [neon.tech](https://neon.tech) — free tier: 0.5 GB storage
2. Create project → copy the **Connection string**:
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

## 2. Render (Backend)

### Setup
1. Go to [render.com](https://render.com) → New → Web Service
2. Connect your GitHub account and select `LakshmiNarayana124/Miniproject5`
3. Render reads `render.yaml` from the root automatically — it sets the build/start commands
4. **Branch:** `clean-start`
5. **Root Directory:** `Backend`
6. **Build Command:** `pip install -r requirements.txt`
7. **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
8. **Health Check Path:** `/auth/registration-status`

### Environment Variables (set in Render dashboard → Environment)

| Variable | Value |
|---|---|
| `INTELLIWATCH_SECRET_KEY` | 64-char hex (`python -c "import secrets; print(secrets.token_hex(32))"`) |
| `DATABASE_URL` | Neon connection string |
| `INTELLIWATCH_CORS_ORIGINS` | `https://intelliwatch-iw.vercel.app` |
| `FIREBASE_PROJECT_ID` | `intelliwatch-66ad0` |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Optional — enables phone OTP verification |

### After deploy
Your backend URL: `https://intelliwatch-backend.onrender.com`

---

## 3. Vercel (Frontend)

### Setup
1. Go to [vercel.com](https://vercel.com) → New Project → Import `Miniproject5`
2. Vercel reads `vercel.json` from the root automatically
3. **Branch:** `clean-start`
4. **Framework Preset:** Vite
5. **Root Directory:** `frontend`

### Environment Variables (set in Vercel dashboard → Settings → Environment Variables)

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://intelliwatch-backend.onrender.com` |
| `VITE_FIREBASE_API_KEY` | `AIzaSyDS_tlmIpoPG-4YeB62RjbPf5BT6x-qu0I` |
| `VITE_FIREBASE_AUTH_DOMAIN` | `intelliwatch-66ad0.firebaseapp.com` |
| `VITE_FIREBASE_PROJECT_ID` | `intelliwatch-66ad0` |
| `VITE_FIREBASE_STORAGE_BUCKET` | `intelliwatch-66ad0.firebasestorage.app` |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | `174724193863` |
| `VITE_FIREBASE_APP_ID` | `1:174724193863:web:e09ddbd891e2cc547d5b62` |

### After deploy
Your frontend URL: `https://intelliwatch-iw.vercel.app`

---

## 4. Firebase Console Setup

1. Firebase Console → Authentication → Sign-in method
2. Enable **Google**
3. Enable **Phone** (requires Blaze plan for SMS)
4. Authentication → Settings → Authorized domains → add `intelliwatch-iw.vercel.app`

---

## 5. Post-Deploy Checklist

- [ ] Render service is running — `GET /auth/registration-status` returns `{"registration_enabled": true}`
- [ ] `DATABASE_URL` is set in Render → tables auto-created on first request
- [ ] `INTELLIWATCH_CORS_ORIGINS` in Render matches Vercel URL exactly (no trailing slash)
- [ ] Firebase authorized domains includes `intelliwatch-iw.vercel.app`
- [ ] `VITE_API_URL` in Vercel points to Render URL (no trailing slash)
- [ ] PWA installable — visit frontend on Android Chrome → "Add to Home Screen"

---

## Redeploy

Push to `clean-start` — both services redeploy automatically.

```powershell
git add .
git commit -m "your change"
git push miniproject5 HEAD:clean-start
# Vercel: ~1 min  |  Render: ~3 min  |  Neon: always on
```

---

## Local Development

### Backend
```powershell
cd Backend
python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `Backend\.env`:
```
INTELLIWATCH_SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=postgresql://...your-neon-url...
INTELLIWATCH_CORS_ORIGINS=http://localhost:5173
FIREBASE_PROJECT_ID=intelliwatch-66ad0
```

```powershell
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
# API docs at http://localhost:8000/docs
```

### Frontend
```powershell
cd frontend && npm install
```

Create `frontend\.env.local`:
```
VITE_API_URL=http://localhost:8000
VITE_FIREBASE_API_KEY=AIzaSyDS_tlmIpoPG-4YeB62RjbPf5BT6x-qu0I
VITE_FIREBASE_AUTH_DOMAIN=intelliwatch-66ad0.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=intelliwatch-66ad0
VITE_FIREBASE_STORAGE_BUCKET=intelliwatch-66ad0.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=174724193863
VITE_FIREBASE_APP_ID=1:174724193863:web:e09ddbd891e2cc547d5b62
```

```powershell
npm run dev
# Open http://localhost:5173
```
