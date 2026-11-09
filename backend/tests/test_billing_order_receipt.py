from app.services.billing_engine import build_order_payload


def test_paid_plan_order_receipts_fit_razorpay_limit_and_remain_unique():
    receipts = [
        build_order_payload("pro", "00000000-0000-0000-0000-000000000001")["receipt"]
        for _ in range(25)
    ]

    assert all(receipt.startswith("solix_") for receipt in receipts)
    assert all(len(receipt) <= 40 for receipt in receipts)
    assert all(receipt.isascii() for receipt in receipts)
    assert len(set(receipts)) == len(receipts)


def test_order_receipt_does_not_replace_tenant_and_plan_notes():
    org_id = "00000000-0000-0000-0000-000000000001"

    payload = build_order_payload("enterprise", org_id)

    assert payload["notes"] == {"org_id": org_id, "plan": "enterprise"}
    assert len(payload["receipt"]) <= 40

