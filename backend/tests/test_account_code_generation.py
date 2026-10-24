from app.routers.accounting import unique_account_code


def test_account_code_preserves_legacy_code_when_available():
    assert unique_account_code("Cash", set()) == "CASH"


def test_account_code_suffixes_colliding_prefixes_without_overflow():
    occupied = {"CASH IN HA", "CASH IN HA-1", "CASH IN HA-2"}
    code = unique_account_code("Cash in hand - branch", occupied)
    assert code == "CASH IN H-3"
    assert len(code) <= 20
    assert code not in occupied


def test_account_code_generation_is_deterministic_for_same_occupied_set():
    occupied = {"ACCOUNTS P", "ACCOUNTS P-1"}
    assert unique_account_code("Accounts payable", occupied) == "ACCOUNTS -2"
