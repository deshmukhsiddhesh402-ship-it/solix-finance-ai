# Solix environment configuration and deployment checklist

This guide documents the explicit application-environment requirement introduced by the security hardening changes. It does not certify a deployment as production-ready.

## Choose the environment explicitly

Set `ENV` to one of the accepted values:

- `development` — local development only.
- `test` — automated tests.
- `staging` — staging deployment.
- `production` — production deployment.

An unset or unknown `ENV` must fail application configuration rather than silently selecting development mode. Do not use `development` or `dev` in a deployed environment.

## OTP delivery

The repository does not provide a configured email/SMS OTP delivery provider by default. OTP delivery must remain fail-closed until a real provider is configured and tested.

- Keep `DEV_OTP_ENABLED=false` in staging and production.
- Never return OTP values from deployed API responses or log them.
- Do not treat a successful OTP-request response as proof that a message was delivered.
- Local OTP disclosure is a local-only convenience and must never be enabled in a deployed environment.

## Production secret and origin checklist

Configure these values through the hosting platform's secret/environment-variable facility; do not commit real secrets:

- `ENV=production`
- `DEV_OTP_ENABLED=false`
- `JWT_SECRET`: a newly generated, high-entropy secret of at least 32 characters; do not reuse the example value.
- `DATABASE_URL`: the real production database connection string, with least-privilege credentials and TLS where supported.
- `ALLOWED_ORIGINS`: explicit HTTPS origins for the deployed frontend only; do not use a wildcard or localhost in production.
- `REDIS_URL`: the intended production Redis endpoint, secured according to the hosting provider's guidance.
- Provider credentials only for services that are actually configured and used.

Because `ALLOWED_ORIGINS` is typed as a list in the settings model, provide it in the format accepted by the installed Pydantic Settings version. For environment-variable configuration, a JSON array such as `["https://app.example.com"]` is the intended shape; validate this in the target deployment environment before release.

Generate a secret locally and store the output directly in your secret manager; do not paste the value into source code or commit it:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Docker Compose caution

The repository's root `docker-compose.yml` is a convenience stack and contains development-oriented database defaults. Do not expose it unchanged to the public internet or assume it is a hardened production deployment. Before using Compose for a real deployment, replace development credentials, configure the required environment explicitly, restrict database/cache network exposure, configure persistent backups and TLS/ingress, and verify health checks and startup behavior. Prefer a separate, reviewed production override or deployment manifest instead of silently changing local-development behavior.

## Pre-release verification

1. Confirm the deployed service reports/uses the intended environment without exposing secrets.
2. Verify startup fails when `ENV` is absent or invalid.
3. Verify production startup rejects missing/weak JWT secrets, a default database URL, invalid origins, and `DEV_OTP_ENABLED=true`.
4. Verify OTP requests fail safely when no delivery provider is configured; confirm no OTP is included in responses or logs.
5. Run focused configuration/authentication tests and the full backend CI suite.
6. Verify database connectivity, migrations, backups, TLS, CORS, monitoring and recovery procedures in the actual target environment.
7. Do not claim production readiness until these checks are completed and reviewed.

This checklist is operational guidance, not a substitute for reviewing the actual hosting configuration, secret store, infrastructure and live deployment.
