-- Ensure the UTC month anchor is stored as the same instant regardless of the
-- PostgreSQL session TimeZone. Migration 004's naive timestamp expression was
-- implicitly cast to TIMESTAMPTZ using the session timezone.
ALTER TABLE subscriptions
    ALTER COLUMN usage_period_start
    SET DEFAULT (date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC');
