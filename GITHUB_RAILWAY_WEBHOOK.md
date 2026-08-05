# GitHub Actions to Railway Webhook Integration

## Auto-Deploy Setup (10 minutes)

### Step 1: Get Railway Webhook URL

1. Railway Dashboard → Project Settings
2. Click **"Webhooks"** tab
3. Copy webhook URL (format: `https://api.railway.app/webhooks/deploy/...`)

### Step 2: Add to GitHub Secrets

1. GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. **Name:** `DEPLOY_WEBHOOK_URL`
4. **Value:** (paste Railway webhook from Step 1)
5. Click **"Add secret"**

### Step 3: Verify Workflow

1. Commit and push to `main` branch
2. GitHub → **Actions** tab
3. Watch workflow run:
   - ✓ Tests pass
   - ✓ Backend image pushed
   - ✓ Frontend image pushed
   - ✓ Deploy webhook called (last step)
4. Railway Dashboard → Check deployment triggered

### What Happens Automatically Now

**On `git push origin main`:**

```
GitHub Actions:
  1. Run backend tests
  2. Run frontend tests
  3. Build backend image → push to ghcr.io
  4. Build frontend image → push to ghcr.io
  5. Call Railway webhook (triggers auto-deploy)

Railway:
  1. Pulls latest images
  2. Deploys backend service
  3. Deploys frontend service
  4. Runs healthchecks
  5. Routes traffic to new version

Total time: ~3-5 minutes
```

---

## Rollback (If Deployment Fails)

1. Railway Dashboard → Service
2. Click **"Deployments"** tab
3. Find previous working deployment
4. Click **"Rollback"** button
5. Confirm

---

## Manual Deploy (Without GitHub)

If you need to deploy manually:

```bash
# Option A: Push latest images
docker pull ghcr.io/your-org/solix-backend:latest
docker pull ghcr.io/your-org/solix-frontend:latest
railway up

# Option B: Trigger webhook manually
curl -X POST https://api.railway.app/webhooks/deploy/[id] \
  -H "Content-Type: application/json"
```

---

## Troubleshooting

### Webhook not triggering

- Check GitHub Actions logs: **Actions** → latest run
- Verify `DEPLOY_WEBHOOK_URL` is set and correct
- Try manual `curl` to webhook URL to test connectivity

### Deploy fails in Railway

- Check Railway logs: Dashboard → Service → Logs
- Common issues:
  - Missing environment variables (add to Railway service settings)
  - Docker image pull failed (check image exists in ghcr.io)
  - Health check timeout (increase timeout in Railway settings)

### Stuck deployment

- Railway Dashboard → Service → **"Abort"** button
- Railway Dashboard → Service → **"Rollback"** to previous version

---

## Disable Auto-Deploy (Temporarily)

1. Comment out or remove `DEPLOY_WEBHOOK_URL` from GitHub secrets
2. Workflow still runs tests and builds, but doesn't call webhook
3. Manual deploy: Use Railway UI or CLI

---

## Enable Manual Approval Before Deploy

Edit `.github/workflows/ci-cd.yml`:

```yaml
  deploy:
    needs: [build-backend, build-frontend]
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    environment:  # Add this to require approval
      name: production
      url: https://solix.yourdomain.com
    steps:
      # ... rest of deploy step
```

Now GitHub requires manual approval (check "Environments" tab) before deploy runs.

---

## Monitor Deployments

### GitHub Actions

- Commit → Actions tab → Watch workflow run

### Railway

- Dashboard → Deployments tab → See history

### Rollback Analytics

Track deployments:

```bash
railway logs --service=backend
railway logs --service=frontend
```

---

## Cost: Zero Additional

- GitHub Actions: Free (2000 min/month included)
- Railway Webhook: Free
- Total: **No extra costs**

The only Railway charges are for the services themselves (postgres, redis, backend, frontend).
