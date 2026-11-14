"""Inventory SKU/name search must treat SQL LIKE metacharacters literally."""


def test_inventory_search_escapes_like_wildcards_and_escape_character():
    from app.routers.accounting import _escape_inventory_search

    assert _escape_inventory_search(r"A%_\\B") == r"A\%\_\\B"


def test_inventory_register_uses_explicit_like_escape_character():
    from app.models.accounting import InventoryItem
    from sqlalchemy import or_

    pattern = "%A\\%\\_%"
    criterion = or_(
        InventoryItem.sku.ilike(pattern, escape="\\"),
        InventoryItem.name.ilike(pattern, escape="\\"),
    )

    compiled = criterion.compile()
    assert " ESCAPE " in str(compiled).upper()
    assert any(value == pattern for value in compiled.params.values())
