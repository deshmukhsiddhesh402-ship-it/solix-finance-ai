# Deployment Guide

## Before deploying

1. Review the tracked environment files and the repository's full history. Rotate every real credential found there; removing a file from a later commit does not remove earlier history.
2. Store production values in the deployment platform's secret manager, never in Git or a Docker image.
3. Configure ENV=production, DATABASE_URL, and a randomly generated JWT_SECRET with at least 32 characters. The backend now refuses the default development database URL or a short/default JWT secret in production.
4. Set ALLOWED_ORIGINS to the exact frontend origins. Configure ANTHROPIC_API_KEY only if Copilot is enabled and Google/Microsoft OAuth values only if those providers are enabled.
5. **OTP delivery is not implemented.** Non-development OTP requests intentionally return 503 until a real email/SMS sender is configured. Do not expose development OTP responses in production.
6. Verify PostgreSQL database/schema.sql against a disposable database first. Versioned Alembic migrations and rollback scripts are not present in the reviewed repository; do not apply unreviewed destructive schema changes to production.

## CI and containers

The current workflow still expects nonexistent solix_minimal/backend and solix_minimal/frontend directories and calls npm ci without a lockfile. It must be corrected before CI can verify a branch. Backend dependencies are declared in backend/requirements.txt; frontend dependencies are declared in frontend/package.json. Docker contexts exclude .env*; supply runtime configuration using platform secrets.

Production image publishing and the optional deployment webhook run only on pushes to main/develop as configured by the workflow. The hardening branch has not been deployed. Review its CI results and merge through the normal repository review process only after the environment-file/credential issue is resolved.

## Current limitations

The current database schema is a single SQL file; no migration verification has been performed. The Copilot's required Anthropic key and OAuth provider credentials are deployment-specific. Banking integrations, email/SMS delivery, and tax rule updates are not configured by this guide.
