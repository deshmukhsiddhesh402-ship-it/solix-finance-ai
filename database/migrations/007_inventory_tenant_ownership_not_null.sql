-- Solix Finance AI — require complete tenant ownership for inventory rows.
-- This migration deliberately refuses to guess ownership for legacy orphan rows.
-- Review and reconcile any NULL values with the business owner before retrying.
-- Do not apply automatically in production.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM inventory_items WHERE org_id IS NULL) THEN
        RAISE EXCEPTION 'Cannot enforce inventory tenant ownership: inventory_items contains rows with NULL org_id; reconcile ownership first.';
    END IF;

    IF EXISTS (SELECT 1 FROM inventory_transactions WHERE item_id IS NULL) THEN
        RAISE EXCEPTION 'Cannot enforce inventory item ownership: inventory_transactions contains rows with NULL item_id; reconcile or remove invalid rows through an approved process first.';
    END IF;
END
$$;

ALTER TABLE inventory_items
    ALTER COLUMN org_id SET NOT NULL;

ALTER TABLE inventory_transactions
    ALTER COLUMN item_id SET NOT NULL;
