"""Inventory ORM metadata must expose indexes used by the ledger migrations."""


def test_inventory_transaction_metadata_declares_ledger_ordering_indexes():
    from app.models.accounting import InventoryTransaction

    indexes = {index.name: index for index in InventoryTransaction.__table__.indexes}

    assert indexes["uq_inventory_transactions_sequence_no"].unique is True
    assert [column.name for column in indexes["uq_inventory_transactions_sequence_no"].columns] == ["sequence_no"]
    assert indexes["idx_inventory_transactions_item_date_sequence"].unique is False
    assert [
        column.name for column in indexes["idx_inventory_transactions_item_date_sequence"].columns
    ] == ["item_id", "txn_date", "sequence_no"]
