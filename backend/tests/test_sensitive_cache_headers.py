from app.main import _is_sensitive_api_path


def test_sensitive_api_paths_are_no_store_candidates():
    assert _is_sensitive_api_path("/api/auth/session")
    assert _is_sensitive_api_path("/api/billing/checkout")
    assert _is_sensitive_api_path("/api/ocr/extract-invoice")


def test_non_sensitive_api_paths_keep_existing_cache_policy():
    assert not _is_sensitive_api_path("/api/health")
    assert not _is_sensitive_api_path("/api/accounting/trial-balance")
