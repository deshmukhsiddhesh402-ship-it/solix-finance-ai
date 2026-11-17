-- Solix Finance AI — add a reversible active/inactive lifecycle flag to fixed assets.
-- Existing fixed assets remain active; no asset values or depreciation history are changed.
-- Review and apply manually after confirming the fixed_assets table is present.

ALTER TABLE fixed_assets
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE fixed_assets
    ALTER COLUMN is_active SET DEFAULT TRUE,
    ALTER COLUMN is_active SET NOT NULL;
