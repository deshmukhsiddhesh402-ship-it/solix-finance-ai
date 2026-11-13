-- Solix Finance AI — idempotent inventory transaction references.
-- References are scoped to an inventory item and protect clients from
-- accidentally posting the same source transaction more than once.
-- Existing transactions remain valid with a NULL reference.
-- Review table size and backup before applying; do not run automatically.

ALTER TABLE inventory_transactions
    ADD COLUMN IF NOT EXISTS reference_no VARCHAR(100);

CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_transactions_item_reference
    ON inventory_transactions(item_id, reference_no)
    WHERE reference_no IS NOT NULL;
