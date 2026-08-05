# CI/CD Pipeline Complete – Solix Finance AI

**GitHub Actions workflow is now live and ready.**

## What's Set Up

✅ **Automated Testing**
- Backend: pytest with postgres + redis services
- Frontend: ESLint + Next.js build validation

✅ **Automated Build & Push**
- Builds on every push to `main` or `develop`
- Pushes to GitHub Container Registry (ghcr.io)
- Smart caching with Docker buildx
- Image tagging: `latest`, branch-based, and commit-based tags

✅ **Code Quality**
- Pre-commit hooks: Black (Python), Prettier (JS/TS), ESLint
- Secrets scanning with detect-secrets
- Automated on every local commit

✅ **Optional Auto-Deploy**
- Webhook-based deployment to Railway/Render/custom services
- Configured via `DEPLOY_WEBHOOK_URL` GitHub secret

---

## Files Created

| File | Purpose |
|------|---------|
| `.github/workflows/ci-cd.yml` | Main GitHub Actions pipeline |
| `.pre-commit-config.yaml` | Local code quality hooks |
| `CI_CD_GUIDE.md` | Detailed CI/CD documentation |
| `CI_CD_QUICK_START.md` | Quick setup instructions |
| `setup-hooks.sh` | One-line pre-commit setup |
| `deploy.sh` | Manual deploy script |
| `k8s-manifest.yaml` | Kubernetes deployment manifests |
| `backend/.env.example` | Backend env template |
| `frontend/.env.local.example` | Frontend env template |

---

## Quick Start

### 1. Enable GitHub Actions (First Time)

```bash
git push solix-repo main
```

Go to **GitHub.com → Solix repo → Actions** → See workflow run

### 2. Set Up Pre-commit Hooks (Local Development)

```bash
bash ./solix_minimal/setup-hooks.sh
```

Now commits are auto-linted before pushing.

### 3. Add Secrets (Optional, for Auto-Deploy)

**GitHub repo → Settings → Secrets and variables → Actions**

```
DEPLOY_WEBHOOK_URL = https://api.railway.app/webhooks/deploy/...
```

### 4. Manual Deploy (Without Auto-Webhook)

```bash
bash ./solix_minimal/deploy.sh all v1.0.0
```

---

## How It Works

### On `git push` to main/develop:

```
1. GitHub Actions triggered
2. Backend tests run (postgres + redis services)
3. Frontend tests run (ESLint + build)
4. If tests pass:
   - Build backend image → push to ghcr.io
   - Build frontend image → push to ghcr.io
5. If DEPLOY_WEBHOOK_URL set:
   - POST to webhook → Railway/Render auto-deploys
```

### On `git push` to any branch (PR):

```
1. Tests only (no build/push)
2. PR reviewers see test results
```

---

## View Build Logs

**GitHub → Actions → [workflow name] → [run number]**

- Click a step to expand logs
- Common issues:
  - Tests fail: Check test output for errors
  - Build fails: Check Docker build logs
  - Push fails: Check registry permissions

---

## Production Deployment Options

### Option A: Railway (Recommended – Easiest)
1. Create Railway project
2. Connect GitHub repo
3. Set environment variables in Railway UI
4. CI/CD pushes images, Railway auto-deploys

### Option B: Kubernetes (kubectl)
```bash
kubectl apply -f solix_minimal/k8s-manifest.yaml
```

### Option C: Manual Server
```bash
docker pull ghcr.io/your-org/solix-backend:latest
docker pull ghcr.io/your-org/solix-frontend:latest
docker compose up -d
```

---

## Next Steps

1. ✅ Push to GitHub to trigger first workflow run
2. ✅ Set up pre-commit hooks: `bash setup-hooks.sh`
3. ⏭️ **Option A:** Configure Railway webhook for auto-deploy
   - **Option B:** Set up Kubernetes + kubectl apply
   - **Option C:** Manual deploy script for VPS/EC2

Need deployment help? Choose one of the options above, and I'll guide you through it.
