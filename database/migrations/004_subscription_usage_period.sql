-- Monthly usage counters need an explicit period anchor; updated_at cannot safely
-- serve as the reset marker because unrelated billing updates also change it.
ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS usage_period_start TIMESTAMPTZ
    NOT NULL DEFAULT date_trunc('month', now());

