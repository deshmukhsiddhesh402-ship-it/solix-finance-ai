# Solix Finance AI

An AI-powered finance & Excel platform for CAs, accounting firms, and finance students.

## Honest scope note
This scaffold gives you a **real, running foundation** plus **one fully working module**
(AI Excel Assistant) end-to-end, plus **working calculation engines** for the Accounting
and Indian Tax modules (trial balance, ratios, GST/TDS/Income Tax). It is not the entire
12-module platform — that is a multi-month build. Use this as the base and we add one
module at a time on top of it, exactly as you build now.

## Stack
- Frontend: Next.js 14 (App Router) + TypeScript + Tailwind CSS + shadcn/ui + Recharts
- Backend: FastAPI (Python) — single backend, no Node duplication
- DB: PostgreSQL (schema in `database/schema.sql`), pgvector for RAG embeddings
- Cache: Redis
- AI: Claude API (Anthropic) as primary/only provider for v1
- Auth: NextAuth.js (Google + Microsoft OAuth) + custom OTP endpoint

## Folder structure
```
solix-finance-ai/
├── frontend/                 # Next.js app
│   ├── app/
│   │   ├── dashboard/
│   │   ├── excel-assistant/  # ✅ fully working module
│   │   ├── accounting/
│   │   ├── tax/
│   │   ├── banking/
│   │   ├── analysis/
│   │   ├── chat/
│   │   └── learning/
│   ├── components/
│   ├── lib/
│   └── package.json
├── backend/                  # FastAPI app
│   ├── app/
│   │   ├── routers/          # excel_ai.py, accounting.py, tax.py
│   │   ├── services/         # claude_service.py, accounting_engine.py, tax_engine.py
│   │   ├── models/           # SQLAlchemy models
│   │   └── core/             # config, security, db session
│   └── requirements.txt
└── database/
    └── schema.sql
```

## Run locally
```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Environment variables
See `backend/.env.example` and `frontend/.env.local.example`.

## Status: all 10 planned modules built
1. ✅ AI Excel Assistant — formula explain/generate/fix, VBA generator, Office Scripts, Pivot Table planner
2. ✅ Accounting core — Journal → Trial Balance → P&L → Balance Sheet, ratios, depreciation (SLM/WDV), FIFO/LIFO/WAVG inventory
3. ✅ Indian Tax — GST calculator + GSTR-3B summary, TDS calculator, Income Tax (new regime, FY2025-26)
4. ✅ Dashboard — **now live**: KPI cards + Recharts pull real data from posted journal entries via `/api/dashboard/summary`, with automatic honest fallback to demo data if nothing's been posted yet or the backend's unreachable. Export to Excel or a one-page PDF summary report (verified: both files generate correctly and round-trip through pandas/pypdf).
5. ✅ Banking reconciliation — amount+date matching, outstanding cheques, deposits-not-credited, BRS statement
6. ✅ Financial Analysis — NPV, IRR (bisection solver), CAGR, Break-even, DCF Valuation, Scenario Analysis — all verified against textbook values
7. ✅ AI Chat / RAG — PDF/Excel/**Word**/text upload, chunking, **real semantic search via Voyage AI embeddings + pgvector** when `VOYAGE_API_KEY` is set, with automatic fallback to TF-IDF keyword retrieval when it isn't. Every answer cites the source document by name.
8. ✅ Excel Automation — auto-clean, dedupe, error detection, rule-based expense categorization, cleaned-file download
9. ✅ Learning Mode — AI tutor + auto-generated quizzes (Excel, Advanced Excel, Tally Prime, Power BI, GST, TDS, ITR, Accounting, Finance, US CMA)
10. ✅ Auth + Deployment — Google/Microsoft OAuth + Email OTP via NextAuth, Dockerfiles, docker-compose, and a full deployment guide (`DEPLOYMENT.md`) for Vercel/Railway/AWS

## Post-launch priority additions (built after the initial 10 modules)
11. ✅ **Real RAG with embeddings** — Voyage AI + pgvector semantic search, with graceful TF-IDF fallback (see "Enabling real semantic RAG" below)
12. ✅ **OCR & Invoice Processing** — Claude vision extracts vendor/GSTIN/amounts from invoice images and PDFs; exports to Excel or a balanced journal entry
13. ✅ **Live Financial Dashboard** — Accounting module now persists journal entries to Postgres; Dashboard computes real KPIs/trends from them, with Excel/PDF export
14. ✅ **AI Finance Copilot** — natural-language queries ("show expenses above ₹50,000", "why did profit decrease", "predict next month's cash flow", "generate GST summary") answered via Claude tool-use: Claude picks which real function to call, the backend executes deterministic math against actual ledger data, and Claude writes the final answer grounded in those real numbers — never invented figures. All four underlying functions (filtering, period-comparison driver analysis, linear-trend cash flow projection, GST summary) are unit-tested against a synthetic multi-month ledger.
15. ✅ **Enterprise Features** — Role-Based Access Control (Admin/Accountant/Auditor) with a real, fail-closed permission matrix (unit-tested, including that garbage role/resource input correctly denies access rather than silently passing); audit logging with field-level before/after diffs (tested for create/edit/delete); multi-company support via a proper `org_memberships` table (a user can be Admin in one company and Auditor in another — not just one global role); API key generation for external integrations using SHA-256 hashing + constant-time verification (tested: keys never collide, tampered keys correctly rejected). Scheduled reports and notifications have real data models and CRUD endpoints, but are honestly flagged as NOT wired to actual execution — see below.
16. ✅ **Mobile app (Expo / React Native)** — a real, working foundation with 3 functional screens (Email OTP login, live Dashboard, AI Finance Copilot chat), all hitting the same FastAPI backend as the web app. NOT full mobile parity with all 12 web modules — see `mobile/README.md` for exactly what's built vs. what's next, and why Expo was chosen over bare React Native or Flutter.
17. ✅ **Subscription Billing (Razorpay)** — chosen over Stripe since it natively supports UPI/netbanking for Indian CA firms. Order creation + Checkout widget integration, and — the security-critical piece — real HMAC-SHA256 webhook and payment signature verification, tested including a simulated tampered-payload attack (correctly rejected) and a forged payment_id (correctly rejected). Three plans (Trial/Pro/Enterprise) with usage-limit gating logic, unit-tested. A pricing page with live Razorpay Checkout is wired on the frontend.

## Enabling real semantic RAG (recommended before production)
By default, AI Chat works out of the box using TF-IDF keyword retrieval — no
extra setup needed. To upgrade to real semantic embeddings:
1. Get a Voyage AI API key (Anthropic's recommended embeddings partner for RAG): https://www.voyageai.com
2. Set `VOYAGE_API_KEY` in `backend/.env`
3. Set a real `DATABASE_URL` pointing at Postgres with the pgvector extension enabled (see `database/schema.sql`)
4. Restart the backend — new uploads automatically switch to semantic mode (the chat UI shows a "Semantic search" badge instead of "Keyword search")

Note: this repo's sandbox couldn't reach a live Postgres instance or the
Voyage API to execute-test this path end-to-end — the code is structurally
correct and the parts that don't need live infra (docx/pdf/xlsx extraction,
chunking, the TF-IDF fallback) are verified. Run `pytest backend/tests` and
do one real upload+ask cycle after deploying to confirm the pgvector path
end-to-end in your environment.

## What's genuinely NOT done (flagged honestly, not faked)
- **Subscription Billing**: the actual Razorpay order-creation API call needs the `razorpay` Python SDK and live network access to `api.razorpay.com`, which this sandbox doesn't have — could not execute-test that specific call. What IS tested: both signature-verification functions (webhook and client-payment), including a simulated attacker tampering with a payment amount (correctly rejected) and forging a payment ID (correctly rejected) — that's the part that actually protects you from fraud, so it got the testing priority. The usage-gating (`check-limit` endpoint) exists but is NOT yet wired into the metered routers (AI Chat upload, Invoice OCR) — it's built and ready to call, but nothing calls it yet. Do one real Razorpay test-mode checkout after deploying.
- **Enterprise Features — execution/delivery layers**: `scheduled_reports` and `notifications` have real database tables and working CRUD endpoints, but creating a scheduled-report row does NOT itself send anything — that needs a background worker (Celery beat is a natural fit given Redis is already in the stack) polling the table and calling `report_export_engine.py` + an email provider at the right time. Similarly, `notifications` are stored and can be marked read, but nothing pushes them out as email/SMS/push — same pattern and same caveat as the OTP module. Building the worker process and wiring a real email/SMS provider is the next concrete step, not something to fake as "done."
- **API integrations**: the request only said "API integrations" without specifics. What's built is the *foundation* — real, hashed API keys that external services could authenticate with — but no actual outbound integrations (Zapier, Tally sync, bank feeds, etc.) exist yet. Tell me which specific integration matters most and I'll build that one properly rather than guessing.
- **RBAC is not yet enforced on the pre-existing routers** (accounting, invoice_ocr, etc.) — the permission matrix and `require_permission` dependency are built and unit-tested, but wiring them into every existing mutating endpoint from earlier passes is follow-up work, not done in this pass.
- **AI Finance Copilot** — the four underlying analysis functions (expense filtering, period-comparison, cash-flow projection, GST summary) are unit-tested and verified correct against synthetic data. The Claude tool-use orchestration (Claude picks a tool → backend executes it → Claude writes the final answer) follows the standard Anthropic tool-use API pattern but could not be execute-tested here (no network to the Claude API in this sandbox) — test one real query per tool type after deploying. Also note: the cash-flow "prediction" is a simple linear-trend extrapolation, not a machine-learning forecast — it says so in its own output, and gets much less reliable with only 1-2 months of history to project from.
- **Live Dashboard + Accounting persistence** — the Accounting module now has a `POST /api/accounting/journal-entries` endpoint that actually saves to Postgres (previously it was fully stateless), and the Dashboard queries that real data. The aggregation math (KPIs, monthly trend, expense breakdown) is unit-tested against a synthetic multi-month ledger — including catching and fixing a real double-counting bug where a "GST Output Payable" account was being counted into both GST Liability and generic Payables. What I could NOT execute-test here: the actual SQLAlchemy DB round-trip (no live Postgres in this sandbox) — do one real "post journal entry → check dashboard" cycle after deploying.
- **OCR & Invoice Processing** — ✅ now built. Uses Claude's vision capability directly (no separate Tesseract/OCR engine) to read invoice images and PDFs, extracting vendor, GSTIN, invoice number/date, tax breakdown, and line items as structured JSON. GSTIN format validation is real and tested; a full check-digit/checksum validator was deliberately left OUT after my own implementation failed to validate known-correct sample GSTINs — shipping a broken validator would silently reject real GSTINs, which is worse than not having one. Use the government GSTN "Search Taxpayer" lookup for authoritative validation. The PDF-rasterization and live vision-API paths could not be execute-tested in this sandbox (no network, PyMuPDF not installable offline) — do one real test upload after deploying.
- **Voice Assistant, Document Scanner UI, Fraud Detection, Cash Flow Prediction** — not built; these are reasonable next additions once the core is validated with real users
- **E-way Bill / E-invoice generation, GSTR-1/GSTR-9 full filing flows** — GST calculation logic exists, but government-portal integration (GSP/ASP APIs) is a separate, compliance-heavy build
- **Multi-tenant billing/subscription logic** — the `organizations` table supports it, but Stripe/Razorpay integration isn't wired
- **Production-grade session storage** — AI Chat and Excel Automation currently use in-memory dicts; swap for Redis/S3 before real traffic (documented in `DEPLOYMENT.md`)

## Run locally (all services)
```bash
docker compose up --build
```
Or run frontend/backend separately — see below.
