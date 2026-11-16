-- Solix Finance AI — preserve inventory history while archiving unused items.
-- Existing rows become active by default. No historical transactions are deleted.
-- Review application and backup before production use; do not run automatically.

ALTER TABLE inventory_items
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
