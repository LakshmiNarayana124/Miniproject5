# IntelliWatch — Deployment Guide

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Vercel     │────▶│   Render      │────▶│    Neon      │
│  (Frontend)  │ API │  (Backend)    │ DB  │  (Postgres)  │
│  React+Vite  │     │  FastAPI      │     │  Serverless │
└──────────────┘     └──────────────┘     └──────────────┘
```

---

## 1. Neon (Database)

### Create
1. Sign up at [neon.tech](https://neon.tech) (free tier: 0.5 GB storage)
2. Create a new project
3. Copy the **Connection string** — it looks like:
   ```
   postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
   ```

### Migrate from SQLite to Neon
```bash
# Set the Neon connection string
set NEON_DIRECT_URL=postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require

# Run the migration (preserves your SQLite DB untouched)
python migrate_sqlite_to_neon.py
```

The script:
- Reads all tables from `Backend/database/intelliwatch.db`
- Converts SQLite DDL to PostgreSQL DDL
- Creates tables in dependency order
- Copies all records
- Recreates indexes
- Resets identity sequences
- Verifies row counts match

---

## 2. Render (Backend)

### Option A — Blueprint (recommended)
1. Push this repo to GitHub
2. In Render dashboard → New → Blueprint
3. Select your repo — Render reads `render.yaml` automatically
4. Set secret env vars:
   - `INTELLIWATCH_SECRET_KEY` — a 64-char random hex string
   - `FIREBASE_SERVICE_ACCOUNT_JSON` — your Firebase service account JSON
5. Deploy

### Option B — Manual
1. Render dashboard → New → Web Service
2. Connect repo, set:
   - **Root Directory**: `Backend`
   - **Build**: `pip install -r requirements.txt`
   - **Start**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free
3. Add env vars as above
4. Deploy

### After deploy
- Your backend URL will be `https://intelliwatch-backend.onrender.com`
- Health check: `GET /auth/registration-status` → `{"registration_enabled": true}`

---

## 3. Vercel (Frontend)

### Deploy
1. Push repo to GitHub (if not already)
2. Go to [vercel.com](https://vercel.com) → New Project
3. Import your repo — Vercel reads `vercel.json` automatically
4. Set env vars:
   - `VITE_API_URL` — your Render backend URL (e.g. `https://intelliwatch-backend.onrender.com`)
   - `VITE_FIREBASE_API_KEY` — from Firebase Console
   - `VITE_FIREBASE_AUTH_DOMAIN`
   - `VITE_FIREBASE_PROJECT_ID`
   - `VITE_FIREBASE_STORAGE_BUCKET`
   - `VITE_FIREBASE_MESSAGING_SENDER_ID`
   - `VITE_FIREBASE_APP_ID`
5. Deploy

### After deploy
- Your frontend URL will be `https://intelliwatch.vercel.app`
- Update `INTELLIWATCH_CORS_ORIGINS` in Render to include this URL

---

## 4. Firebase Console Setup

### Enable sign-in methods
1. Firebase Console → Authentication → Sign-in method
2. Enable **Google**
3. Enable **Phone** — add test phone numbers if needed
4. Add authorized domains:
   - `intelliwatch.vercel.app`
   - `intelliwatch-backend.onrender.com`

### Get the service account key (for backend)
1. Firebase Console → Project Settings → Service Accounts
2. Click "Generate new private key" → downloads a JSON file
3. Set `FIREBASE_SERVICE_ACCOUNT_JSON` in Render to the file contents (or file path)

---

## 5. Environment Variables Summary

| Variable | Where | Required | Description |
|---|---|---|---|
| `INTELLIWATCH_SECRET_KEY` | Render | Yes | 64-char hex string for JWT |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Render | For Firebase login | Service account JSON |
| `INTELLIWATCH_CORS_ORIGINS` | Render | Yes | Vercel frontend URL |
| `NEON_DIRECT_URL` | Local only | For migration | Neon connection string |
| `VITE_API_URL` | Vercel | Yes | Render backend URL |
| `VITE_FIREBASE_*` | Vercel | For Firebase | Firebase web config |

---

## 6. Postgres Support for Backend

The backend currently uses SQLite by default. To use Neon Postgres in production:

1. Install psycopg: `pip install psycopg[binary]`
2. Set `NEON_DIRECT_URL` env var on Render
3. The migration script handles the schema transfer
4. The backend's `database.py` can be adapted to use Postgres by replacing
   `sqlite3.connect()` with `psycopg.connect()` — or use an ORM like SQLAlchemy
   for a smoother transition

### Quick adapter approach
For minimal changes, set `DATABASE_URL` (Postgres) in the environment and
add a conditional in `database.get_connection()`:
```python
import os
def get_connection():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        import psycopg
        conn = psycopg.connect(db_url)
        return conn
    # ... existing SQLite code
```

---

## 7. Free Tier Limits

| Service | Free Tier |
|---|---|
| Render | 750 hours/month (web service sleeps after 15 min idle) |
| Vercel | 100 GB bandwidth, unlimited deployments |
| Neon | 0.5 GB storage, branching included |
| Firebase | generous free tier for Auth (10k/day phone, unlimited Google) |
