# Solix Production Security Gaps

This file records verified implementation gaps so code presence is not confused with integration or production readiness.

## API keys

The repository has API-key generation, SHA-256 hashing, constant-time verification, masking, creation, listing, and revocation. At the current validated HEAD there is **no separate external/integration API endpoint that consumes an API key**. The API-key verifier is therefore intentionally not wired into an invented endpoint. A future external API should add a reusable dependency that authenticates the key first, resolves its organization from the key record, rejects revoked keys, updates \`last_used_at\`, and performs RBAC after authentication.

## Database tenant migration

The requested path \`database/migrations/002_organization_tenant_isolation.sql\` does **not exist at the validated HEAD**. The current \`database/schema.sql\` already defines organization-scoped tables and the \`org_memberships\` uniqueness constraint. No migration was created or applied automatically because there is no existing 002 migration to validate and production database state is not available through the repository.

## Other integration caveats

- Scheduled reports currently persist schedule definitions; a background worker is not wired to send them.
- Notifications are in-app records; external email/SMS/push delivery is not wired.
- OCR and Excel-cleaning intermediate sessions use process memory and should move to shared durable storage before multi-instance production deployment.
- Tax calculations remain deterministic in the tax engine; the UI/AI layer must not be treated as the statutory authority. The repository's documented FY defaults require verification before filing.

These are intentionally documented rather than hidden behind claims of production readiness.
