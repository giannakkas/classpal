# Railway Deployment Guide — ClassPal

## Prerequisites
- Railway account (railway.app)
- GitHub repo: https://github.com/giannakkas/classpal.git
- Domain: classpal.ai
- Cloudflare R2 bucket created
- Stripe account with products/prices created
- Anthropic API key

## Step 1: Create Railway Project

1. Go to railway.app → New Project
2. Name: `classpal`

## Step 2: Add PostgreSQL

1. In your project: + New → Database → PostgreSQL
2. Copy the `DATABASE_URL` from the Variables tab
3. **Important:** For the backend, you need the `asyncpg` variant:
   - Replace `postgresql://` with `postgresql+asyncpg://` in the backend env var

## Step 3: Add Redis

1. + New → Database → Redis
2. Copy the `REDIS_URL`

## Step 4: Deploy Backend (API)

1. + New → GitHub Repo → Select `giannakkas/classpal`
2. Settings:
   - **Root Directory:** `backend`
   - **Builder:** Dockerfile
   - **Start Command:** (leave empty — Dockerfile handles it)
3. Variables — add ALL from `backend/.env.example`:
   ```
   DATABASE_URL=postgresql+asyncpg://...  (from step 2, with +asyncpg)
   REDIS_URL=redis://...                   (from step 3)
   JWT_SECRET=<generate: openssl rand -hex 32>
   CORS_ORIGINS=https://classpal.ai
   ANTHROPIC_API_KEY=sk-ant-...
   R2_ACCOUNT_ID=...
   R2_ACCESS_KEY_ID=...
   R2_SECRET_ACCESS_KEY=...
   R2_BUCKET_NAME=classpal-papers
   R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
   R2_PUBLIC_URL=https://papers.classpal.ai
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   STRIPE_SOLO_PRICE_ID=price_...
   STRIPE_PRO_PRICE_ID=price_...
   RESEND_API_KEY=re_...
   SENTRY_DSN=https://...
   ```
4. Networking → Generate Domain → set custom domain: `api.classpal.ai`
5. Deploy

## Step 5: Deploy Worker (Celery)

1. + New → GitHub Repo → Select `giannakkas/classpal`
2. Settings:
   - **Root Directory:** `backend`  (same code as API)
   - **Builder:** Dockerfile
   - **Dockerfile Path:** `Dockerfile`
   - **Start Command Override:** `celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2`
3. Variables: Copy ALL variables from the backend service
   - Railway lets you reference variables: `${{backend.DATABASE_URL}}`
4. **No networking needed** — worker doesn't serve HTTP
5. Deploy

## Step 6: Deploy Frontend

1. + New → GitHub Repo → Select `giannakkas/classpal`
2. Settings:
   - **Root Directory:** `frontend`
   - **Builder:** Nixpacks (auto-detects Next.js)
3. Variables:
   ```
   NEXT_PUBLIC_API_URL=https://api.classpal.ai
   NEXT_PUBLIC_APP_NAME=ClassPal
   NEXT_PUBLIC_R2_PUBLIC_URL=https://papers.classpal.ai
   ```
4. Networking → Generate Domain → set custom domain: `classpal.ai`
5. Deploy

## Step 7: Configure Domains

### In Cloudflare DNS (or your DNS provider):
```
classpal.ai       → CNAME → <railway-frontend-domain>.up.railway.app
api.classpal.ai   → CNAME → <railway-backend-domain>.up.railway.app
```

### R2 Custom Domain (for paper images):
In Cloudflare dashboard → R2 → Your bucket → Settings → Custom Domain:
```
papers.classpal.ai → Your R2 bucket
```

## Step 8: Stripe Webhook

1. In Stripe Dashboard → Developers → Webhooks
2. Add endpoint: `https://api.classpal.ai/api/billing/webhook`
3. Select events:
   - `checkout.session.completed`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
4. Copy webhook signing secret → update `STRIPE_WEBHOOK_SECRET` in Railway

## Step 9: Run Initial Migration

The backend Dockerfile runs `alembic upgrade head` on every start.
On first deploy, it will create all tables.

To generate the initial migration locally:
```bash
cd backend
alembic revision --autogenerate -m "initial_schema"
# Commit the migration file
git add alembic/versions/
git commit -m "Initial migration"
git push
```

## Step 10: Create First Admin User

Register through the app, then promote via Railway's PostgreSQL console:
```sql
UPDATE users SET role = 'super_admin' WHERE email = 'chris@classpal.ai';
```

## Service Architecture on Railway

```
┌──────────────────────────────────────────────┐
│                Railway Project               │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Frontend │  │ Backend  │  │  Worker  │  │
│  │ Next.js  │  │ FastAPI  │  │ Celery   │  │
│  │ :3000    │  │ :8000    │  │ (no port)│  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │              │              │        │
│       │         ┌────┴─────┐       │        │
│       │         │ Postgres │←──────┘        │
│       │         └──────────┘                │
│       │         ┌──────────┐                │
│       └─────────│  Redis   │←───────────────│
│                 └──────────┘                │
│                                              │
│  External:                                   │
│  ├── Cloudflare R2 (papers.classpal.ai)    │
│  ├── Anthropic API (AI grading)             │
│  ├── Stripe (billing)                       │
│  ├── Resend (email)                         │
│  └── Sentry (monitoring)                    │
└──────────────────────────────────────────────┘
```

## Estimated Monthly Cost (Early Stage)

| Service    | Estimated |
|-----------|-----------|
| Frontend  | ~$5       |
| Backend   | ~$10      |
| Worker    | ~$15      |
| PostgreSQL| ~$5       |
| Redis     | ~$5       |
| **Total** | **~$40**  |

Plus external services:
- R2: Free tier (10GB storage, no egress fees)
- Anthropic: ~$0.02/paper × volume
- Stripe: 2.9% + $0.30 per transaction
- Resend: Free tier (3k emails/month)
- Sentry: Free tier
