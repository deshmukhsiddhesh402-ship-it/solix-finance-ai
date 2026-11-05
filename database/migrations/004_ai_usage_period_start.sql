-- Add an explicit month bucket so AI usage counters reset atomically.
ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS usage_period_start DATE
    NOT NULL DEFAULT (date_trunc('month', now())::date);
