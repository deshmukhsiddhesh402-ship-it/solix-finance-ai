# Security Report

## Findings from revision 8319a1f

- **Critical exposure risk:** backend/.env, backend/.env.production, frontend/.env.local, and frontend/.env.production are tracked in a public repository. Their contents were not inspected or reproduced. GitHub reported no open secret-scanning alerts in the queried endpoint, which does not prove the files contain no secrets. Treat any real credentials there as exposed; rotate them and move values to deployment secrets. A root .gitignore was absent.
- **High — authentication:** OTP was always returned in API JSON and printed in logs; the store was process-local and allowed unlimited guesses. The default JWT secret was weak and accepted in production.
- **High — tenant isolation:** journal writes trusted caller org_id; Copilot queried journal data without company scope; enterprise handlers could authorize one organization and write to another; notification reads/writes trusted arbitrary user IDs.
- **High — route availability:** LedgerLineIn was referenced before definition, creating an import-time failure risk.
- **Medium — image build exposure:** Docker ignore rules did not consistently exclude all .env* files, including production-named files.
- **High — frontend dependency exposure:** the repository pins Next.js 14.2.15. Replit's security policy blocked installation of this version for a critical-vulnerability rule. The vendor's July 2026 security release lists patched versions on the 15.5 maintenance and 16.2 active-LTS lines; upgrading needs an application compatibility review and is not included here.

## Changes in the hardening branch

OTP generation/verification controls, fail-closed production delivery behavior, production JWT/database configuration checks, scoped/permission-checked journal and Copilot routes, organization binding for selected enterprise writes, owner-only notifications, journal audit insertion, environment-file ignore rules, Docker-context exclusions, and regression tests were added.

## Residual risks — do not claim production-secure yet

- The four tracked environment files and their history remain unchanged pending credential review/rotation. Do not merge or deploy until values have been audited and any real credentials rotated.
- OTP state remains in process memory and no provider is configured. Production OTP login returns 503 by design; multi-worker rate limiting is not implemented.
- Other APIs (including dashboard, chat, banking, OCR, tax, and billing) have not been proven to enforce user/company permissions. No RLS policies were found in the reviewed schema.
- Audit-log rows are not protected by database append-only permissions/triggers; not every mutating route writes audit events.
- Local backend tests, compileall, and the CI flake8 selection passed. GitHub Actions ran zero jobs, so there is no CI verification. Frontend lint/build remains blocked by the Next.js 14.2.15 package policy failure; see TEST_REPORT.md.
