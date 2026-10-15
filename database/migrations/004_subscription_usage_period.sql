-- Monthly usage counters need an explicit UTC period anchor; updated_at cannot safely
-- serve as the reset marker because unrelated billing updates also change it.
ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS usage_period_start TIMESTAMPTZ
    NOT NULL DEFAULT timezone('UTC', date_trunc('month', timezone('UTC', now())));

