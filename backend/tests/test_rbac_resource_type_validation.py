from app.services.rbac_engine import has_permission


def test_rbac_fails_closed_for_non_string_resource_values():
    assert has_permission("admin", [], "view") is False
    assert has_permission("admin", {}, "view") is False
    assert has_permission("admin", None, "view") is False


def test_rbac_preserves_valid_resource_permission_checks():
    assert has_permission("admin", "journal_entry", "view") is True
    assert has_permission("auditor", "journal_entry", "delete") is False
