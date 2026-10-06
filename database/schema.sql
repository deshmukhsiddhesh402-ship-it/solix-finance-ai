-- =====================================================================
-- Solix Finance AI — Core Database Schema (PostgreSQL 15+)
-- Enable pgvector for RAG embeddings used by the AI Chat module.
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- ---------------------------------------------------------------------
-- USERS & ORGANIZATIONS (multi-tenant: one CA firm = one organization)
-- ---------------------------------------------------------------------
CREATE TABLE organizations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    gstin           VARCHAR(15),
    pan             VARCHAR(10),
    plan            VARCHAR(20) NOT NULL DEFAULT 'trial', -- trial, pro, enterprise
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id          UUID REFERENCES organizations(id) ON DELETE CASCADE,
    email           VARCHAR(255) UNIQUE NOT NULL,
    full_name       VARCHAR(255),
    auth_provider   VARCHAR(20) NOT NULL DEFAULT 'otp', -- google, microsoft, otp
    role            VARCHAR(20) NOT NULL DEFAULT 'member', -- owner, admin, member, student
    hashed_password VARCHAR(255),              -- null when OAuth
    otp_code        VARCHAR(6),
    otp_expires_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- ACCOUNTING MODULE
-- ---------------------------------------------------------------------
CREATE TABLE chart_of_accounts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id          UUID REFERENCES organizations(id) ON DELETE CASCADE,
    code            VARCHAR(20) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    account_type    VARCHAR(20) NOT NULL, -- asset, liability, equity, income, expense
    parent_id       UUID REFERENCES chart_of_accounts(id),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    UNIQUE (org_id, code)
);

CREATE TABLE journal_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id          UUID REFERENCES organizations(id) ON DELETE CASCADE,
    entry_date      DATE NOT NULL,
    narration       TEXT,
    reference_no    VARCHAR(50),
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE journal_lines (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    journal_id      UUID REFERENCES journal_entries(id) ON DELETE CASCADE,
    account_id      UUID REFERENCES chart_of_accounts(id),
    debit           NUMERIC(18,2) NOT NULL DEFAULT 0,
    credit          NUMERIC(18,2) NOT NULL DEFAULT 0,
    gst_rate_pct    NUMERIC(5,2),
    gst_type        VARCHAR(10),
    gst_taxable_value NUMERIC(18,2),
    tds_section     VARCHAR(10),
    tds_rate        NUMERIC(5,2),
    tds_amount      NUMERIC(18,2),
    CHECK (debit >= 0 AND credit >= 0),
    CHECK (gst_rate_pct IS NULL OR (gst_rate_pct >= 0 AND gst_rate_pct <= 100)),
    CHECK (gst_type IS NULL OR gst_type IN ('IGST', 'CGST', 'SGST', 'NONE')),
    CHECK (gst_taxable_value IS NULL OR gst_taxable_value >= 0),
    CHECK (tds_rate IS NULL OR (tds_rate >= 0 AND tds_rate <= 100)),
    CHECK (tds_amount IS NULL OR tds_amount >= 0)
);

CREATE TABLE fixed_assets (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id              UUID REFERENCES organizations(id) ON DELETE CASCADE,
    asset_name          VARCHAR(255) NOT NULL,
    purchase_date       DATE NOT NULL,
    cost                NUMERIC(18,2) NOT NULL,
    salvage_value       NUMERIC(18,2) NOT NULL DEFAULT 0,
    useful_life_years   INT NOT NULL,
    depreciation_method VARCHAR(20) NOT NULL DEFAULT 'straight_line' -- straight_line, wdv
);

CREATE TABLE inventory_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id          UUID REFERENCES organizations(id) ON DELETE CASCADE,
    sku             VARCHAR(50) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    costing_method  VARCHAR(10) NOT NULL DEFAULT 'FIFO' -- FIFO, LIFO, WAVG
);

CREATE TABLE inventory_transactions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    item_id         UUID REFERENCES inventory_items(id) ON DELETE CASCADE,
    txn_type        VARCHAR(10) NOT NULL, -- purchase, sale
    txn_date        DATE NOT NULL,
    quantity        NUMERIC(18,4) NOT NULL,
    unit_cost       NUMERIC(18,4)
);

-- ---------------------------------------------------------------------
-- INDIAN TAX MODULE
-- ---------------------------------------------------------------------
CREATE TABLE gst_returns (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id          UUID REFERENCES organizations(id) ON DELETE CASCADE,
    return_type     VARCHAR(10) NOT NULL, -- GSTR1, GSTR3B, GSTR9
    period          VARCHAR(7) NOT NULL,  -- e.g. 2026-06
    total_taxable_value NUMERIC(18,2),
    total_tax_liability  NUMERIC(18,2),
    filed_at        TIMESTAMPTZ
);

CREATE TABLE tds_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id          UUID REFERENCES organizations(id) ON DELETE CASCADE,
    section         VARCHAR(10) NOT NULL, -- e.g. 194C, 194J
    deductee_name   VARCHAR(255),
    deductee_pan    VARCHAR(10),
    amount_paid     NUMERIC(18,2) NOT NULL,
    tds_rate        NUMERIC(5,2) NOT NULL,
    tds_amount      NUMERIC(18,2) NOT NULL,
    deposit_date    DATE
);

-- ---------------------------------------------------------------------
-- BANKING MODULE
-- ---------------------------------------------------------------------
CREATE TABLE bank_statements (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id          UUID REFERENCES organizations(id) ON DELETE CASCADE,
    bank_name       VARCHAR(255),
    account_no      VARCHAR(50),
    txn_date        DATE NOT NULL,
    description     TEXT,
    amount          NUMERIC(18,2) NOT NULL,
    txn_type        VARCHAR(10) NOT NULL, -- credit, debit
    mode            VARCHAR(10),          -- RTGS, NEFT, IMPS, UPI, CHEQUE
    reconciled      BOOLEAN NOT NULL DEFAULT false,
    matched_journal_id UUID REFERENCES journal_entries(id)
);

-- ---------------------------------------------------------------------
-- AI CHAT / RAG MODULE
-- ---------------------------------------------------------------------
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id          UUID REFERENCES organizations(id) ON DELETE CASCADE,
    uploaded_by     UUID REFERENCES users(id),
    file_name       VARCHAR(255),
    file_type       VARCHAR(20), -- xlsx, pdf, bank_statement, gst_return
    storage_path    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text      TEXT NOT NULL,
    embedding       vector(1536)
);

CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id          UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id),
    title           VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chat_messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            VARCHAR(10) NOT NULL, -- user, assistant
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_journal_lines_account ON journal_lines(account_id);\nCREATE INDEX idx_journal_lines_gst_tag ON journal_lines(gst_type, gst_rate_pct);\nCREATE INDEX idx_journal_lines_tds_tag ON journal_lines(tds_section, tds_rate);
CREATE INDEX idx_journal_entries_org_date ON journal_entries(org_id, entry_date);
CREATE INDEX idx_bank_statements_org ON bank_statements(org_id, txn_date);
CREATE INDEX idx_doc_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------
-- ENTERPRISE FEATURES: multi-company membership, audit log, API keys,
-- scheduled reports, notifications
-- ---------------------------------------------------------------------
CREATE TABLE org_memberships (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    org_id      UUID REFERENCES organizations(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL DEFAULT 'accountant', -- admin, accountant, auditor
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, org_id)
);

CREATE TABLE audit_logs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id      UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id     UUID,
    action      VARCHAR(20) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id   VARCHAR(100),
    changes     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_logs_org_created ON audit_logs(org_id, created_at DESC);

CREATE TABLE api_keys (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id              UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name                VARCHAR(100) NOT NULL,
    hashed_key          VARCHAR(64) NOT NULL UNIQUE,
    key_prefix_display  VARCHAR(30) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at        TIMESTAMPTZ,
    revoked             BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE scheduled_reports (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id             UUID REFERENCES organizations(id) ON DELETE CASCADE,
    report_type        VARCHAR(30) NOT NULL,
    frequency          VARCHAR(20) NOT NULL, -- daily, weekly, monthly
    recipient_emails   JSONB NOT NULL,
    is_active          BOOLEAN NOT NULL DEFAULT true,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_sent_at       TIMESTAMPTZ
);

CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id      UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id     UUID,
    title       VARCHAR(200) NOT NULL,
    body        TEXT,
    is_read     BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read);

-- ---------------------------------------------------------------------
-- SUBSCRIPTION BILLING (Razorpay)
-- ---------------------------------------------------------------------
CREATE TABLE subscriptions (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id                      UUID REFERENCES organizations(id) ON DELETE CASCADE UNIQUE,
    plan                        VARCHAR(20) NOT NULL DEFAULT 'trial', -- trial, pro, enterprise
    status                      VARCHAR(20) NOT NULL DEFAULT 'active', -- active, past_due, cancelled
    razorpay_order_id           VARCHAR(100),
    razorpay_payment_id         VARCHAR(100),
    current_period_end          TIMESTAMPTZ,
    ai_chat_uploads_this_month  INT NOT NULL DEFAULT 0,
    invoice_ocr_this_month      INT NOT NULL DEFAULT 0,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
