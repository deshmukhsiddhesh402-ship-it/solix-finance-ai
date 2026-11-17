-- Solix Finance AI — add a reversible active/inactive lifecycle flag to inventory items.
-- Existing inventory items remain active; no transaction history is changed.
-- Review and apply manually after confirming the inventory_items table is present.

ALTER TABLE inventory_items
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE inventory_items
    ALTER COLUMN is_active SET DEFAULT TRUE,
    ALTER COLUMN is_active SET NOT NULL;
