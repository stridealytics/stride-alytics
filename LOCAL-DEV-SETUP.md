# Local Development Setup

A quick-start guide for running the full StrideAlytics stack locally: FastAPI backend + Vite/React frontend, with optional Supabase integration.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| [uv](https://docs.astral.sh/uv/) | latest | `pip install uv` or `winget install astral-sh.uv` |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| npm | 9+ | bundled with Node |

---

## 1. Clone & first-time setup

```powershell
git clone <repo-url>
cd stride-alytics
```

For a one-shot setup of all dependencies, run the setup script:

```powershell
# Windows
.\scripts\setup-dev.ps1

# macOS / Linux
bash scripts/setup-dev.sh
```

Or set up each layer manually (sections below).

---

## 2. Backend (FastAPI — port 8000)

### 2a. Install dependencies

```powershell
cd backend
uv sync
```

### 2b. Configure environment

```powershell
cp .env.example .env
# then open .env and fill in values
```

Key variables in `backend/.env`:

```env
# App
DEBUG=true
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Database
# Leave DATABASE_URL commented out → uses in-memory SQLite (easiest for local dev)
# Uncomment and fill to connect to Supabase Postgres:
# DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_REF.supabase.co:5432/postgres

# Supabase Auth (optional — needed only if testing auth flows)
# SUPABASE_URL=https://YOUR_REF.supabase.co
# SUPABASE_ANON_KEY=
# SUPABASE_SERVICE_ROLE_KEY=
# SUPABASE_JWT_SECRET=
```

> **Tip:** `DATABASE_URL` unset → SQLite. Set it → Supabase Postgres. No other change needed.

### 2c. Start the server

```powershell
# Full mode: runs lint + type-check, then starts uvicorn with file-watch reload
uv run dev

# Fast mode: skip verify, start uvicorn directly
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend is ready at **http://localhost:8000**  
Interactive API docs: **http://localhost:8000/docs**

---

## 3. Frontend (Vite + React — port 3000)

### 3a. Install dependencies

```powershell
cd frontend
npm ci
```

### 3b. Configure environment

```powershell
cp .env.example .env.local
# .env.local is git-ignored; edit it freely
```

Key variables in `frontend/.env.local`:

```env
# Points the frontend at the local backend
VITE_API_URL=http://localhost:8000

# Skips Supabase auth checks in the browser during local dev
VITE_DEV_AUTH_BYPASS=true
```

> **Note:** The frontend never needs Supabase credentials — not in local dev, not in production.
> All auth and data access is proxied through the FastAPI backend. The browser only ever
> receives a JWT from the backend; it never talks to Supabase directly.

### 3c. Start the dev server

```powershell
npm run dev
```

Frontend is ready at **http://localhost:3000**

---

## 4. Connecting to Supabase

The frontend never needs Supabase credentials. Only the **backend** holds them.

### 4a. Database (Supabase Postgres)

1. Open your project at [supabase.com/dashboard](https://supabase.com/dashboard).
2. Go to **Project → Settings → Database → Connection string → URI**.
3. Copy the **Transaction pooler** URL (port `6543`) — better for dev connection limits.
4. Set it as `DATABASE_URL` in `backend/.env.local`.

### 4b. Auth (Supabase Auth proxy)

The backend proxies login/signup to Supabase on behalf of the frontend. Add these to `backend/.env.local`:

```env
SUPABASE_URL=https://YOUR_REF.supabase.co
SUPABASE_ANON_KEY=your-anon-public-key    # Dashboard → Settings → API → anon public
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key  # Dashboard → Settings → API → service_role
SUPABASE_JWT_SECRET=your-jwt-secret       # Dashboard → Settings → API → JWT Secret
```

Auth flow (frontend never sees Supabase):
```
Browser → POST /auth/login (email + password)
        → Backend proxies to Supabase Auth using SUPABASE_ANON_KEY
        → Returns JWT to browser
        → Browser attaches JWT to all future API requests
```

---

## 5. Running both at once (two terminals)

```powershell
# Terminal 1 — backend
cd backend && uv run dev

# Terminal 2 — frontend
cd frontend && npm run dev
```

---

## 6. Useful commands

| Task | Command |
|------|---------|
| Backend lint + type-check | `cd backend && uv run verify` |
| Backend tests | `cd backend && uv run pytest tests -q` |
| Frontend type-check + lint | `cd frontend && npm run verify` |
| Frontend tests | `cd frontend && npm test` |
| Frontend production build | `cd frontend && npm run build` |
| Alpha pipeline (dry run) | `cd alpha && uv run python app/main.py --dry-run` |

---

## 7. Troubleshooting

**`VIRTUAL_ENV` warning on backend start**  
The warning `VIRTUAL_ENV=... does not match the project environment path` is harmless — uv ignores it and uses the correct `.venv`.

**Port already in use**  
Kill the existing process or change the port:
```powershell
# Change backend port
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
# Change frontend port (vite.config.ts or --port flag)
npm run dev -- --port 3001
```

**Frontend can't reach backend (`Network Error`)**  
Make sure `VITE_API_URL` in `frontend/.env.local` matches the port uvicorn is actually running on. The fallback default is `http://localhost:8000`.

**Supabase connection refused**  
Use the **Transaction pooler** connection string (port `6543`), not the direct connection (port `5432`), which may be blocked by firewalls on some networks.
