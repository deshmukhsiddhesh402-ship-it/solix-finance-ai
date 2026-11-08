"""Regression tests for controlled validation errors from tax API routes."""

import pytest
from fastapi import HTTPException

from app.routers import tax


def test_gst_calculation_route_maps_engine_validation_to_422():
    request = tax.GstRequest(
        taxable_value=-1,
        gst_rate_pct=18,
        is_interstate=False,
    )

    with pytest.raises(HTTPException) as exc:
        tax.gst_calculate(request)

    assert exc.value.status_code == 422
    assert "taxable_value" in exc.value.detail


def test_gstr3b_route_maps_engine_validation_to_422():
    request = tax.Gstr3bRequest(lines=[], input_tax_credit=-1)

    with pytest.raises(HTTPException) as exc:
        tax.gst_gstr3b(request)

    assert exc.value.status_code == 422
    assert "input_tax_credit" in exc.value.detail


def test_income_tax_route_maps_engine_validation_to_422():
    request = tax.IncomeTaxRequest(gross_salary=-1, other_income=0)

    with pytest.raises(HTTPException) as exc:
        tax.income_tax_new_regime(request)

    assert exc.value.status_code == 422
    assert "gross_salary" in exc.value.detail


def test_valid_gst_route_response_is_unchanged():
    request = tax.GstRequest(
        taxable_value=1000,
        gst_rate_pct=18,
        is_interstate=True,
    )

    response = tax.gst_calculate(request)

    assert response["igst"] == 180.0
    assert response["cgst"] == 0.0
    assert response["sgst"] == 0.0
    assert response["invoice_total"] == 1180.0



def test_income_tax_response_labels_the_financial_year_of_its_slab_constants():
    response = tax.income_tax_new_regime(
        tax.IncomeTaxRequest(gross_salary=900000, other_income=0)
    )

    assert response["financial_year"] == "2025-26"
    assert response["tax_regime"] == "new"
    assert response["taxable_income"] == 825000.0
