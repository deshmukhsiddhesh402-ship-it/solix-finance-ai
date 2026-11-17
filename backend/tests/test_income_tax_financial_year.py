"""Regression tests for the supported income-tax financial-year contract."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.tax import router
from app.services.tax_engine import (
    SUPPORTED_NEW_REGIME_FINANCIAL_YEAR,
    calculate_income_tax_new_regime,
)


app = FastAPI()
app.include_router(router, prefix="/api/tax")
client = TestClient(app)


def test_income_tax_engine_accepts_the_explicit_supported_year():
    result = calculate_income_tax_new_regime(
        1_200_000,
        financial_year=SUPPORTED_NEW_REGIME_FINANCIAL_YEAR,
    )

    assert result["taxable_income"] == 1_125_000
    assert result["total_tax_payable"] == 0


@pytest.mark.parametrize("financial_year", ["2026-27", "2024-25", "", None, 2025])
def test_income_tax_engine_rejects_unsupported_year_values(financial_year):
    with pytest.raises(ValueError, match="supported only for FY 2025-26"):
        calculate_income_tax_new_regime(1_200_000, financial_year=financial_year)


def test_income_tax_api_rejects_unsupported_financial_year_with_422():
    response = client.post(
        "/api/tax/income-tax/new-regime",
        json={"gross_salary": 1_200_000, "financial_year": "2026-27"},
    )

    assert response.status_code == 422


def test_income_tax_api_keeps_legacy_requests_on_the_explicit_default_year():
    response = client.post(
        "/api/tax/income-tax/new-regime",
        json={"gross_salary": 1_200_000},
    )

    assert response.status_code == 200
    assert response.json()["calculation_status"] == "reference_only"
    assert response.json()["filing_ready"] is False


def test_income_tax_api_marks_explicit_supported_year_as_reference_only():
    response = client.post(
        "/api/tax/income-tax/new-regime",
        json={"gross_salary": 1_200_000, "financial_year": "2025-26"},
    )

    assert response.status_code == 200
    assert response.json()["calculation_status"] == "reference_only"
    assert response.json()["filing_ready"] is False
