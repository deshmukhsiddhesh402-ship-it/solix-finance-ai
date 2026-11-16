-- Solix Finance AI — prevent duplicate inventory SKUs within an organization.
-- Existing duplicates are not renamed automatically; reconcile them against source
-- item masters before applying this index. Do not run automatically in production.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM inventory_items
        GROUP BY org_id, sku
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'Cannot enforce inventory SKU uniqueness: duplicate (org_id, sku) values exist; reconcile them first.';
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_items_org_sku
    ON inventory_items(org_id, sku);
