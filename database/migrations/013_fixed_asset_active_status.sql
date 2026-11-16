-- Solix Finance AI — add reversible soft-archive state to fixed assets.
-- Existing fixed assets remain active; no financial history is deleted.
-- Review and apply manually after backup; do not run automatically in production.

ALTER TABLE fixed_assets
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
