-- Solix Finance AI — stable ordering for same-day inventory transactions.
-- Adds a database-generated insertion sequence used by the inventory ledger
-- and persisted FIFO/LIFO/weighted-average valuation.
-- Existing rows receive sequence values during ALTER TABLE; their original
-- same-day business order cannot be reconstructed from the old schema.
-- Review table size and schedule this DDL for an appropriate maintenance
-- window. Do not run this automatically in production.

ALTER TABLE inventory_transactions
    ADD COLUMN IF NOT EXISTS sequence_no BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_transactions_sequence_no
    ON inventory_transactions(sequence_no);

CREATE INDEX IF NOT EXISTS idx_inventory_transactions_item_date_sequence
    ON inventory_transactions(item_id, txn_date, sequence_no);
