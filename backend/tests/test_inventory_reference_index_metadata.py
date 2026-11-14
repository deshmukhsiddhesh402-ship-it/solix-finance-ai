"""Ensure ORM metadata matches the inventory source-reference uniqueness migration."""


def test_inventory_transaction_metadata_declares_partial_reference_index():
    from app.models.accounting import InventoryTransaction

    index = next(
        index for index in InventoryTransaction.__table__.indexes
        if index.name == "uq_inventory_transactions_item_reference"
    )

    assert index.unique is True
    assert [column.name for column in index.columns] == ["item_id", "reference_no"]
    assert "reference_no IS NOT NULL" in str(index.dialect_options["postgresql"]["where"])
    assert "reference_no IS NOT NULL" in str(index.dialect_options["sqlite"]["where"])
