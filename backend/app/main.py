"""
Solix Finance AI — FastAPI backend entrypoint.
Run: uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import excel_ai, accounting, tax, banking, analysis, chat, excel_automation, learning, auth, invoice_ocr, dashboard, copilot, enterprise, billing
from app.core.config import settings

app = FastAPI(
    title="Solix Finance AI API",
    description="AI-powered finance, accounting, and Excel automation backend.",
    version="0.1.0",
)

# CORS: allow the Next.js frontend to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(excel_ai.router, prefix="/api/excel-ai", tags=["AI Excel Assistant"])
app.include_router(accounting.router, prefix="/api/accounting", tags=["Accounting"])
app.include_router(tax.router, prefix="/api/tax", tags=["Indian Tax"])
app.include_router(banking.router, prefix="/api/banking", tags=["Banking"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Financial Analysis"])
app.include_router(chat.router, prefix="/api/chat", tags=["AI Chat / RAG"])
app.include_router(excel_automation.router, prefix="/api/excel-automation", tags=["Excel Automation"])
app.include_router(learning.router, prefix="/api/learning", tags=["Learning Mode"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(invoice_ocr.router, prefix="/api/ocr", tags=["OCR & Invoice Processing"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Live Dashboard"])
app.include_router(copilot.router, prefix="/api/copilot", tags=["AI Finance Copilot"])
app.include_router(enterprise.router, prefix="/api/enterprise", tags=["Enterprise Features"])
app.include_router(billing.router, prefix="/api/billing", tags=["Subscription Billing"])


@app.get("/api/health", tags=["System"])
def health_check():
    """Simple liveness check used by Docker/Railway health probes."""
    return {"status": "ok", "service": "solix-finance-ai-backend"}
