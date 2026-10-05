# Test Report

## Baseline at reviewed revision

- GitHub Actions run 31115335044 for commit 8319a1fa3f4a684e53ea18e4d7f014d009499a21: **failure**.
- The workflow used nonexistent solix_minimal/ working directories and npm ci without a committed frontend/package-lock.json; these are concrete workflow defects.
- Existing backend/tests/test_engines.py contained 13 calculation tests, with no authentication or cross-company API tests at baseline.

## Hardening branch — commit 8fdb185

- Python 3.12 command pytest tests -v from backend/: **18 passed**, including all 13 calculation tests and five new OTP/config/router regressions. One existing Pydantic deprecation warning was emitted.
- Python compileall over backend/app and backend/tests: **passed**.
- CI-equivalent lint command flake8 app --count --select=E9,F63,F7,F82 --show-source --statistics: **passed**, zero selected errors.
- GitHub Actions run 37006250860 for the PR commit: **failure with zero jobs** (event was push); it did not execute tests. The existing workflow's branch filters and invalid paths remain unchanged because the workflow-file write returned 404.
- Frontend install, lint, and production build: **not run**. The pinned Next.js 14.2.15 package was blocked by Replit's security firewall under its critical-vulnerability policy. The app's dependencies were not changed to bypass the block.

## Scope and remaining checks

Tests ran in a sparse checkout of the exact branch commit with tracked environment files excluded. No PostgreSQL service was available, so no database integration, migration, or live API/tenant-isolation test ran. Docker, browser/mobile, OAuth, email delivery, deployment, and full frontend checks remain unverified. The backend test suite is a scoped regression check, not proof of production readiness.
