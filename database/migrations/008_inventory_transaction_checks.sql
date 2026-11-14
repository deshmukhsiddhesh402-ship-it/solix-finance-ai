-- Solix Finance AI — enforce valid inventory transaction types and amounts.
-- Refuse to add constraints when legacy rows violate the intended posting shape.
-- Reconcile exceptions using source documents; do not rewrite accounting history automatically.
-- Review table size/locking and backups before production application.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM inventory_transactions
        WHERE txn_type NOT IN ('purchase', 'sale')
    ) THEN
        RAISE EXCEPTION 'Cannot constrain inventory txn_type: unsupported legacy values exist.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM inventory_transactions
        WHERE quantity <= 0
    ) THEN
        RAISE EXCEPTION 'Cannot constrain inventory quantity: zero or negative legacy quantities exist.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM inventory_transactions
        WHERE unit_cost < 0
    ) THEN
        RAISE EXCEPTION 'Cannot constrain inventory unit_cost: negative legacy costs exist.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM inventory_transactions
        WHERE NOT (
            (txn_type = 'purchase' AND unit_cost IS NOT NULL) OR
            (txn_type = 'sale' AND unit_cost IS NULL)
        )
    ) THEN
        RAISE EXCEPTION 'Cannot constrain inventory cost shape: legacy purchase/sale cost combinations require review.';
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_inventory_transaction_type') THEN
        ALTER TABLE inventory_transactions
            ADD CONSTRAINT ck_inventory_transaction_type CHECK (txn_type IN ('purchase', 'sale'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_inventory_transaction_quantity_positive') THEN
        ALTER TABLE inventory_transactions
            ADD CONSTRAINT ck_inventory_transaction_quantity_positive CHECK (quantity > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_inventory_transaction_unit_cost_nonnegative') THEN
        ALTER TABLE inventory_transactions
            ADD CONSTRAINT ck_inventory_transaction_unit_cost_nonnegative CHECK (unit_cost IS NULL OR unit_cost >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_inventory_transaction_cost_shape') THEN
        ALTER TABLE inventory_transactions
            ADD CONSTRAINT ck_inventory_transaction_cost_shape CHECK (
                (txn_type = 'purchase' AND unit_cost IS NOT NULL) OR
                (txn_type = 'sale' AND unit_cost IS NULL)
            );
    END IF;
END
$$;
