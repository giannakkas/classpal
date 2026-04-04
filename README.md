# ClassPal

AI-powered paper grading platform for teachers. Scan student papers, let AI read and grade handwritten answers, review corrections, and export naturally-marked PDFs.

## Architecture

```
classpal/
├── backend/          # FastAPI + Celery (Python)
├── frontend/         # Next.js (TypeScript)
├── worker/           # Celery worker config (shares backend code)
└── .github/          # CI/CD workflows
```

## Tech Stack

- **Frontend:** Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, Fabric.js
- **Backend:** FastAPI, SQLAlchemy, Alembic, Celery, Redis
- **AI:** Anthropic Claude Vision API, Google Cloud Vision (fallback)
- **Storage:** Cloudflare R2 (S3-compatible)
- **Database:** PostgreSQL
- **Deployment:** Railway (monorepo with per-service root directories)

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 15+
- Redis 7+

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # Edit with your values
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Worker (separate terminal)
```bash
cd backend
source venv/bin/activate
celery -A app.tasks.celery_app worker --loglevel=info
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local  # Edit with your values
npm run dev
```

## Railway Deployment

Each service points to its subfolder via Railway's root directory setting:

| Service | Root Directory | Start Command |
|---------|---------------|---------------|
| frontend | `frontend` | `npm start` |
| backend | `backend` | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2` |
| worker | `backend` | `celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2` |

Plus Railway-managed PostgreSQL and Redis.

## License

Proprietary — Venushub CY LTD
