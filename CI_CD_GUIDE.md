# GitHub Actions Secrets Guide for Solix Finance AI

## Required Secrets

### 1. Container Registry (automatic)
- `GITHUB_TOKEN` – Pre-configured, allows push to ghcr.io

### 2. Deployment (optional, for auto-deploy)
- `DEPLOY_WEBHOOK_URL` – Webhook URL from Railway/Render/custom deployment service

Add these in GitHub repo **Settings → Secrets and variables → Actions**

## Example Deployment URLs

### Railway
```
https://api.railway.app/webhooks/deploy/[project-id]/[environment-id]?token=[railway-token]
```

### Render
```
https://api.render.com/deploy/srv-[service-id]?key=[render-deploy-key]
```

### Custom Webhook
```
https://your-deployment-service.com/deploy?token=[token]
```

## GitHub Actions Workflow Triggers

| Branch | Trigger | Action |
|--------|---------|--------|
| `main` | Push | Test → Build → Push to registry → Deploy |
| `develop` | Push | Test → Build → Push to registry (no auto-deploy) |
| Any | Pull Request | Test only (no build/push) |

## Local Setup (Pre-commit Hooks)

```bash
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

## Image Tagging Strategy

Images are tagged automatically:

- `latest` – Latest main branch build
- `develop-[short-sha]` – Latest develop build
- `main-[short-sha]` – Latest main build
- `v1.0.0` – Semantic version tags (when you push git tags)

Example: `ghcr.io/your-org/solix-backend:latest`

## Accessing Built Images

```bash
# Authenticate
echo ${{ secrets.GITHUB_TOKEN }} | docker login ghcr.io -u USERNAME --password-stdin

# Pull
docker pull ghcr.io/your-org/solix-backend:latest
docker pull ghcr.io/your-org/solix-frontend:latest

# Run locally
docker compose -f docker-compose.yml up
```

## Troubleshooting

### Tests fail in CI but pass locally?
- Check Python version: GitHub Actions uses 3.12 by default
- Check environment variables in `.github/workflows/ci-cd.yml`
- Run locally: `docker compose up` to test against real services

### Build fails with "insufficient permissions"?
- Ensure GitHub Actions has "Write packages" permission
  - Settings → Actions → General → Workflow permissions → Check "Read and write permissions"

### Webhook deploy doesn't trigger?
- Verify `DEPLOY_WEBHOOK_URL` secret is set and valid
- Check deploy service logs for failed requests
- Temporarily remove the webhook step for testing: set `if: false`
