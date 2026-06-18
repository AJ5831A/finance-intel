# Deployment & Containerization

## Overview

Ledger is packaged as two Docker containers — a Python/FastAPI backend and a React/Nginx frontend — orchestrated by Docker Compose. The design targets single-host deployment on a small VM or cloud instance, with a named volume for persistent data.

---

## Architecture

```
Internet / Browser
       ↓
   port 8080
  [Frontend Container]
  nginx:alpine
  serves React SPA (dist/)
       ↓ API calls to port 8000
  [Backend Container]
  python:3.13-slim
  Uvicorn (single worker)
       ↓
  [ledger-data volume]
  /data/contracts.db    ← SQLite database
  /data/uploads/        ← uploaded files
```

---

## Docker Services

### Backend — `backend/Dockerfile`

**Base image:** `python:3.13-slim`

Build steps:
1. Copy `requirements-prod.txt`
2. `pip install` all production dependencies
3. Copy application source
4. Set `WORKDIR /app`

Run command:
```
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

**Critical: single worker only.** The in-process progress store (`pipeline/progress.py`) and Python `BackgroundTasks` are not shared across workers. Multiple workers would cause progress polling to fail randomly and background tasks to conflict.

**Persistent volume:** `/data` mounted from `ledger-data`
- `DB_PATH=/data/contracts.db`
- `UPLOAD_DIR=/data/uploads`

**Port exposed:** `8000`

---

### Frontend — `frontend/Dockerfile`

**Multi-stage build:**

**Stage 1 — Build** (`node:20-alpine`):
```dockerfile
COPY package*.json .
RUN npm ci
COPY . .
ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build
```

**Stage 2 — Serve** (`nginx:alpine`):
```dockerfile
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

`VITE_API_BASE` must be passed as a **build argument** — Vite inlines environment variables at compile time. It cannot be changed at runtime without rebuilding.

**Port exposed:** `80` (mapped to host `8080` in Compose)

---

## Nginx Configuration

**File:** `frontend/nginx.conf`

Simple SPA config:
- Serves files from `/usr/share/nginx/html`
- `try_files $uri $uri/ /index.html` — sends all unknown paths to `index.html` (required for React Router client-side routing)
- Listens on port `80`

---

## Docker Compose

**File:** `docker-compose.yml`

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ledger-data:/data
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.5-flash}
      - DB_PATH=/data/contracts.db
      - UPLOAD_DIR=/data/uploads

  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_BASE: ${VITE_API_BASE:-http://localhost:8000}
    ports:
      - "8080:80"
    depends_on:
      - backend

volumes:
  ledger-data:
```

---

## Environment Variables

### Required

| Variable | Service | Purpose |
|----------|---------|---------|
| `GEMINI_API_KEY` | backend | Google Gemini API key (secret) |

### Optional

| Variable | Service | Default | Purpose |
|----------|---------|---------|---------|
| `GEMINI_MODEL` | backend | `gemini-2.5-flash` | Gemini model ID |
| `DB_PATH` | backend | `contracts.db` | SQLite file path |
| `UPLOAD_DIR` | backend | `uploads` | Upload directory |
| `VITE_API_BASE` | frontend (build arg) | `http://localhost:8000` | Backend public URL |

Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_key_here
VITE_API_BASE=http://your-server-ip:8000
```

---

## Deployment Options

### Option 1: Single-Host Docker (Recommended)

Best for: $5–10/month VMs (Hetzner CX22, DigitalOcean Basic, etc.)

```bash
# Clone repo
git clone <repo>
cd finance-intel

# Set env vars
echo "GEMINI_API_KEY=your_key" > .env
echo "VITE_API_BASE=http://<your-server-ip>:8000" >> .env

# Build and start
docker compose up -d --build

# Access
# Frontend: http://<server-ip>:8080
# Backend API: http://<server-ip>:8000
```

### Option 2: Managed Split

- **Frontend:** Vercel or Netlify (free tier, instant global CDN)
- **Backend:** Render, Fly.io, or Railway (requires persistent disk)
- Set `VITE_API_BASE` to the backend's public URL at build time

### Option 3: Bare VM (No Docker)

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements-prod.txt
GEMINI_API_KEY=xxx uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm ci && VITE_API_BASE=http://localhost:8000 npm run build
# Serve dist/ with nginx or any static file server
```

---

## Key Constraints & Limitations

| Constraint | Reason | Implication |
|-----------|--------|-------------|
| Single backend instance | In-process progress store + BackgroundTasks | Cannot horizontally scale without Redis |
| Persistent disk required | SQLite + uploaded files stored locally | Serverless/ephemeral hosts not viable |
| Long-running requests | Large 10-Ks can take minutes to analyze | Serverless functions (Vercel, Lambda) timeout too quickly |
| `VITE_API_BASE` is build-time | Vite inlines env vars at compile | Must rebuild frontend image when backend URL changes |

---

## Data Persistence

The `ledger-data` named Docker volume stores:
- `contracts.db` — all document metadata and analysis results
- `uploads/` — all uploaded PDF/DOCX files

Data survives:
- Container restarts
- `docker compose down` (volume is not removed)

Data is removed by:
- `docker compose down -v` (explicitly removes volumes)
- Manual `docker volume rm ledger_ledger-data`

---

## Production Checklist

- [ ] `GEMINI_API_KEY` set in environment
- [ ] `VITE_API_BASE` set to public backend URL (not `localhost`)
- [ ] CORS origin in `main.py` tightened from `*` to frontend domain
- [ ] HTTPS configured (reverse proxy like Caddy or Nginx with Let's Encrypt)
- [ ] Volume backup strategy in place for `ledger-data`
- [ ] `GEMINI_MODEL` set appropriately (flash for speed, pro for quality)
