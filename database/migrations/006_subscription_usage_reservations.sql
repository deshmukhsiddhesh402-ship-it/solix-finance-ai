-- Track each quota reservation so compensation is request-scoped and idempotent.
-- Additive only: this migration does not rewrite existing subscription counters.
CREATE TABLE IF NOT EXISTS subscription_usage_reservations (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    usage_key VARCHAR(64) NOT NULL
        CHECK (usage_key IN ('ai_chat_uploads_this_month', 'invoice_ocr_this_month')),
    period_start TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    released_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_usage_reservations_org_period
    ON subscription_usage_reservations (org_id, period_start);
