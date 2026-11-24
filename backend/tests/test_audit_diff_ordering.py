from app.services.audit_engine import diff_fields


def test_diff_fields_returns_deterministic_key_order():
    before = {"zeta": 1, "alpha": 2, "middle": 3}
    after = {"zeta": 4, "alpha": 5, "middle": 6}
    first = diff_fields(before, after)
    second = diff_fields(dict(reversed(list(before.items()))), dict(reversed(list(after.items()))))
    assert list(first) == ["alpha", "middle", "zeta"]
    assert first == second


def test_diff_fields_handles_added_and_removed_keys_in_stable_order():
    result = diff_fields({"z": 1, "b": 2}, {"c": 3, "a": 4})
    assert list(result) == ["a", "b", "c", "z"]
