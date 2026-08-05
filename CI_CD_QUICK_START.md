# Quick Start Guide for CI/CD

## 1. Enable GitHub Actions

1. Push repo to GitHub
2. Go to **Settings → Actions → General**
3. Check "Allow all actions and reusable workflows"
4. Check "Read and write permissions" (for container registry push)

## 2. Add Required Secrets (if deploying auto-deploy)

**Settings → Secrets and variables → Actions**

- `DEPLOY_WEBHOOK_URL` (optional) – For Railway/Render webhook

## 3. View Workflow Runs

- **Actions tab** → See build status for each push/PR
- Click workflow to see logs

## 4. Expected Behavior

### On Push to `main`
```
✓ Backend tests
✓ Frontend tests
✓ Build & push backend image
✓ Build & push frontend image
✓ Deploy (if webhook configured)
```

### On Push to `develop`
```
✓ Backend tests
✓ Frontend tests
✓ Build & push backend image (tagged: develop-[sha])
✓ Build & push frontend image (tagged: develop-[sha])
(No auto-deploy)
```

### On Pull Request
```
✓ Backend tests
✓ Frontend tests
(No build/push, no deploy)
```

## 5. Pull Built Images Locally

```bash
# Authenticate with GitHub
echo ${{ secrets.GITHUB_TOKEN }} | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# Pull latest
docker pull ghcr.io/YOUR_ORG/solix-backend:latest
docker pull ghcr.io/YOUR_ORG/solix-frontend:latest

# Or use docker-compose with image override
docker compose -f docker-compose.prod.yml up
```

## 6. Set Up Local Pre-commit Hooks

```bash
# One-time setup
bash ./solix_minimal/setup-hooks.sh

# Now commits are linted automatically
git add .
git commit -m "your message"
# ESLint, Black, and other checks run automatically
```

## 7. Debug Workflow Issues

- Check **Actions → [workflow name] → [run]** for full logs
- Look for red X marks indicating failed steps
- Common issues:
  - Tests fail: Check test output, ensure DB/Redis services in CI config
  - Build fails: Check Docker build logs, verify Dockerfile syntax
  - Push fails: Check container registry permissions, GITHUB_TOKEN scope

## 8. Configure Auto-Deploy (Optional)

### Railway Example
1. Go to Railway project
2. **Settings → Webhooks**
3. Copy webhook URL
4. Add to GitHub secrets as `DEPLOY_WEBHOOK_URL`
5. Next push to `main` triggers auto-deploy

### Manual Deploy
1. Built images are in GitHub Container Registry (ghcr.io)
2. SSH into your server
3. Run: `docker pull ghcr.io/YOUR_ORG/solix-backend:latest`
4. Run: `docker compose up -d`
