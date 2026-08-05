# Solix Finance AI — Laptop Test Package

This package is the web/full-stack version for testing on a laptop.

## Included
- Next.js frontend
- FastAPI backend
- PostgreSQL + pgvector schema
- Redis via Docker Compose
- Backend test suite

## Not included
- React Native mobile app (kept out to reduce transfer size; can be restored from the original ZIP)
- Deployment documentation

## Start
1. Install Docker Desktop.
2. Open this folder in VS Code.
3. Copy `backend/.env.example` to `backend/.env`.
4. Copy `frontend/.env.local.example` to `frontend/.env.local`.
5. Run:

```bash
docker compose up --build
```

6. Open `http://localhost:3000`.

Backend health: `http://localhost:8000/api/health`
API docs: `http://localhost:8000/docs`

External AI, OAuth, email, and payment integrations require their own credentials for live testing.
