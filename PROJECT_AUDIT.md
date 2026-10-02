# Solix Finance AI — Project Audit

**Reviewed revision:** 8319a1fa3f4a684e53ea18e4d7f014d009499a21 on main  
**Scope:** GitHub source tree and API-visible workflow metadata. No Replit project was mounted in this conversation and no local repository checkout was available; this is a source audit, not a production penetration test.

## Repository and architecture

- 188 entries in the reviewed Git tree; Next.js 14 / React 18 frontend and FastAPI / SQLAlchemy backend.
- PostgreSQL schema is defined in database/schema.sql. Alembic is a dependency, but no versioned migration directory is present in the reviewed tree.
- Source includes accounting, GST/TDS calculations, banking reconciliation, dashboard, OCR, Excel tools, enterprise membership/RBAC, and a finance copilot.
- The only committed backend test module at the reviewed revision is backend/tests/test_engines.py. It covers calculation examples, not API authentication or tenant isolation.
- Four non-example environment files are tracked. No root .gitignore existed at the reviewed revision. Their contents were deliberately not read; treat their values as potentially exposed until reviewed and rotated.
- The only observed GitHub Actions run for the reviewed revision concluded with failure. The workflow referred to solix_minimal/backend and solix_minimal/frontend, while those directories are absent from the tree. It also called npm ci without a committed frontend lockfile.

## Confirmed high-priority defects

1. backend/app/routers/accounting.py annotated a route with LedgerLineIn before defining the model. Python evaluates the annotation at import time, so loading the application could fail.
2. OTP request code returned the OTP unconditionally and wrote it to logs. Verification used an in-memory store without an attempt limit or resend cooldown.
3. The default JWT secret was a known development string with no production startup guard.
4. Journal posting accepted a caller-supplied organization ID without authentication or membership validation.
5. Copilot queried journal entries without an organization filter and had no permission dependency.
6. Enterprise membership/API-key/scheduled-report handlers authorized a query-string organization but separately trusted an organization in the body. Notification endpoints trusted caller-supplied user IDs and lacked authorization.
7. EmailStr is used but email-validator was not listed as a backend dependency.

## Accounting and tax limitations

- The accounting engine uses binary floating-point arithmetic and journal-line inputs did not reject negative, zero, or simultaneous debit/credit amounts.
- Posting has no idempotency key, reversal workflow, financial-year lock, or complete immutable audit trail.
- GST logic is limited to a basic intra/inter-state split and simplified GSTR-3B netting. GSTIN/place-of-supply validation, UTGST/cess, effective-date tax rules, GSTR-1, and Rule 88A allocation are not implemented in the reviewed engine.
- TDS rates are constants rather than effective-date/FY-aware rules; thresholds and several deductor/deductee distinctions are absent. These values must not be treated as current filing advice.
- No bank-statement persistence/import/reconciliation history or month-end close workflow was verified by this source review.

## Status

The first hardening slice is on an isolated branch. Implemented changes and tests are recorded in IMPLEMENTATION_LOG.md; verified results and unresolved risks are in TEST_REPORT.md and SECURITY_REPORT.md. Remaining modules still require a route-by-route tenant/auth audit before production use.
