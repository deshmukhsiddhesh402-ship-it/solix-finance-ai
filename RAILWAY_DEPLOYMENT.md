# Railway Deployment – Solix Finance AI

**Live Deployment Guide for Railway**

Railway is the easiest path to production. This guide takes you from zero to live in ~10 minutes.

---

## Prerequisites

- GitHub repo with Solix code
- Railway account (https://railway.app) – sign up with GitHub
- Docker images pushed to GitHub Container Registry (CI/CD already configured)

---

## Step 1: Create Railway Project

1. Go to https://railway.app/dashboard
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize and select your Solix repo
5. Railway scaffolds a project

---

## Step 2: Add PostgreSQL Service

1. In Railway project, click **"+ Add"**
2. Search **"PostgreSQL"** → Select version 16
3. Railway creates managed database
4. Once running, click on the postgres service
5. Copy connection string from **"Connect"** tab
   - Format: `postgresql://user:password@host:port/database`

---

## Step 3: Add Redis Service

1. Click **"+ Add"** again
2. Search **"Redis"** → Select version 7
3. Once running, copy connection string
   - Format: `redis://host:port`

---

## Step 4: Deploy Backend Service

1. Click **"+ Add"** → **"Empty Service"**
2. Name: `solix-backend`
3. Configure:
   - **Builder:** Dockerfile
   - **Dockerfile path:** `solix_minimal/backend/Dockerfile`
   - **Port:** 8000

4. Once deployed, go to **Settings** of backend service
5. Click **"Environment"** and add variables:

```
DATABASE_URL=<postgres connection from step 2>
REDIS_URL=<redis connection from step 3>
ANTHROPIC_API_KEY=<your claude api key>
JWT_SECRET=<generate: openssl rand -base64 32>
ENVIRONMENT=production
LOG_LEVEL=INFO
```

6. Redeploy: Click **"Redeploy"** in service menu

---

## Step 5: Deploy Frontend Service

1. Click **"+ Add"** → **"Empty Service"**
2. Name: `solix-frontend`
3. Configure:
   - **Builder:** Dockerfile
   - **Dockerfile path:** `solix_minimal/frontend/Dockerfile`
   - **Port:** 3000

4. Go to **Settings** → **Environment**
5. Add variables:

```
NEXT_PUBLIC_BACKEND_URL=https://<solix-backend-railway-url>:8000
NEXTAUTH_URL=https://<solix-frontend-railway-url>
NEXTAUTH_SECRET=<generate: openssl rand -base64 32>
GOOGLE_CLIENT_ID=<your oauth id>
GOOGLE_CLIENT_SECRET=<your oauth secret>
```

6. Redeploy

---

## Step 6: Enable Auto-Deploy from GitHub

### Option A: Railway GitHub Integration (Recommended)

1. Go to Railway project **Settings**
2. Find **"GitHub"** section
3. Click **"Connect GitHub"**
4. Select repo + branches to auto-deploy
5. Check **"Auto-deploy on push"**

Now every push to `main` auto-deploys.

### Option B: Webhook from GitHub Actions (More Control)

1. In Railway, go to **Project** → **Settings** → **Webhooks**
2. Copy webhook URL
3. Add to GitHub repo **Settings → Secrets → Actions**:
   ```
   DEPLOY_WEBHOOK_URL=<railway webhook>
   ```

CI/CD already configured to call this webhook on push to `main`.

---

## Step 7: Set Up Custom Domain (Optional)

1. Go to frontend service
2. Click **"Public URL"** tab
3. Click **"Add custom domain"**
4. Enter your domain (e.g., `solix.yourdomain.com`)
5. Add DNS record:
   - **Type:** CNAME
   - **Name:** `solix`
   - **Value:** `<railway-provided-cname>`
6. Wait 5-10 mins for DNS propagation
7. Access at `https://solix.yourdomain.com`

---

## Step 8: Verify Deployment

```bash
# Backend health
curl https://<solix-backend-url>/api/health

# Frontend (should return HTML)
curl https://<solix-frontend-url>

# View logs
# Dashboard → Service → Logs tab
```

---

## Monitoring & Logs

### View Logs in Railway

1. Dashboard → Service name → **"Logs"** tab
2. Real-time streaming
3. Search/filter by keywords

### Set Alerts

1. Service → **"Monitoring"** tab
2. Create alert for CPU/memory/errors
3. Alerts notify via email

---

## Scaling

### Auto-scaling (Coming to Railway)

Currently Railway scales containers manually:

1. Service → **"Settings"** → **"Scale"**
2. Increase replicas for load balancing

### Database Scaling

PostgreSQL starts small, auto-scales:
- CPU threshold: Auto-upgrades if needed
- Storage: Auto-expands (charges per GB)

### Redis Scaling

For high throughput:
1. Postgres service → **"Settings"** → **"Plan"**
2. Upgrade from shared to dedicated instance

---

## Troubleshooting

### Deploy Failed

1. Check **Logs** tab for error
2. Common issues:
   - Missing environment variable → Add to service Settings
   - Dockerfile path wrong → Check path matches repo structure
   - Build timeout → Increase timeout in service settings (Project → Settings → Build)

### Backend can't connect to PostgreSQL

1. Verify `DATABASE_URL` format in backend environment
2. Check PostgreSQL service is running (green status)
3. Restart backend service: **"Redeploy"** button

### Frontend can't reach backend

1. Check `NEXT_PUBLIC_BACKEND_URL` includes full https URL
2. Backend service must be public (has public URL)
3. Test: `curl https://<backend-url>/api/health` from local machine

### 502 Bad Gateway

- Backend service crashed or not listening on 8000
- Check logs: Service → Logs
- Restart: **"Redeploy"**

---

## Cost Estimate (Monthly)

| Service | Tier | Cost |
|---------|------|------|
| Backend | $5 | ~$5 |
| Frontend | $5 | ~$5 |
| PostgreSQL | Starter (1GB) | ~$15 |
| Redis | Starter | ~$5 |
| **Total** | | ~**$30/month** |

Costs scale with usage. Free tier covers light development.

---

## Next Steps

1. ✅ Create Railway account
2. ✅ Create project from GitHub
3. ✅ Add Postgres + Redis
4. ✅ Deploy backend + frontend
5. ✅ Add environment variables
6. ✅ Test live URLs
7. ⏭️ Set custom domain (optional)
8. ⏭️ Enable auto-deploy webhook

**Live in ~10 mins. No DevOps needed.**
