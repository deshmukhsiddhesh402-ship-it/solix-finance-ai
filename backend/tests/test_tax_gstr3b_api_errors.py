"""API regression tests for GSTR-3B validation error mapping."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.tax import router

app = FastAPI()
app.include_router(router, prefix="/api/tax")
client = TestClient(app)


def test_gstr3b_invalid_line_returns_422_instead_of_500():
    response = client.post(
        "/api/tax/gst/gstr3b-summary",
        json={
            "lines": [
                {
                    "taxable_value": -1,
                    "gst_rate_pct": 18,
                    "is_interstate": False,
                }
            ],
            "input_tax_credit": 0,
        },
    )

    assert response.status_code == 422
    assert "taxable_value" in response.json()["detail"]
