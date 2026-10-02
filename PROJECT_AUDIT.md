# Solix Finance AI — Project Audit

**Reviewed revision:** 8319a1fa3f4a684e53ea18e4d7f014d009499a21 on main  
**Hardening branch:** agent/solix-hardening-2026-10-02, commit 8fdb1859c3ee64964b745324b16325daf38d17ca (plus report refresh pending)  
**Scope:** GitHub source tree/API metadata and a sparse local checkout that excluded all tracked environment files. This is not a production penetration test.

## Repository and architecture

- 188 entries in the reviewed Git tree; Next.js 14 / React 18 frontend and FastAPI / SQLAlchemy backend.
- PostgreSQL schema is defined in database/schema.sql. Alembic is a dependency, but no versioned migration directory is present in the reviewed tree.
- Source includes accounting, GST/TDS calculations, banking reconciliation, dashboard, OCR, Excel tools, enterprise membership/RBAC, and a finance copilot.
- Baseline backend tests cover calculation examples, not API authentication or tenant isolation.
- Four non-example environment files are tracked. Their contents were not read, checked out, changed, or printed. Treat any real credentials there as potentially exposed until reviewed and rotated.
- Existing CI paths reference nonexistent solix_minimal directories and use npm ci without a committed frontend lockfile. The PR workflow run completed with zero jobs; no code tests were run by GitHub Actions.
- The frontend pins Next.js 14.2.15. The package security firewall blocked installing that version; the vendor's current security release lists patched maintenance/active targets on 15.5 and 16.2. A major-version upgrade needs compatibility review and is not included.

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

## Verified hardening-branch checks

- Python 3.12 backend tests: 18 passed, one existing Pydantic deprecation warning.
- CI-equivalent flake8 command: passed with zero selected errors.
- Python compileall over backend/app and backend/tests: passed.
- Frontend lint/build: not run; pinned Next.js package install was blocked by the security firewall.
- GitHub Actions: run 37006250860 completed with failure and zero jobs, so it did not test the PR.

The security and compliance audit remains incomplete for the other API modules. See SECURITY_REPORT.md, TEST_REPORT.md, IMPLEMENTATION_LOG.md, and DEPLOYMENT_GUIDE.md for the scoped changes, verified results, and remaining production blockers.
