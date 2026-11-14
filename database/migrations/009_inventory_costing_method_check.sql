-- Solix Finance AI — restrict inventory costing methods to supported engine values.
-- Refuse to change historical rows automatically; reconcile unsupported methods first.
-- Review constraint validation locks and backups before production application.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM inventory_items
        WHERE costing_method NOT IN ('FIFO', 'LIFO', 'WAVG')
    ) THEN
        RAISE EXCEPTION 'Cannot constrain inventory costing_method: unsupported legacy values exist; reconcile them first.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'inventory_items'::regclass
          AND conname = 'ck_inventory_item_costing_method'
    ) THEN
        ALTER TABLE inventory_items
            ADD CONSTRAINT ck_inventory_item_costing_method
            CHECK (costing_method IN ('FIFO', 'LIFO', 'WAVG'));
    END IF;
END
$$;
