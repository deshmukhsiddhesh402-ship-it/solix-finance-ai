-- Prevent one Razorpay payment from being recorded against multiple tenants.
-- Preflight intentionally fails without modifying data if historical duplicates exist.
DO $$
BEGIN
    IF EXISTS (
        SELECT razorpay_payment_id
        FROM subscriptions
        WHERE razorpay_payment_id IS NOT NULL
        GROUP BY razorpay_payment_id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Cannot enforce unique Razorpay payment IDs: duplicate non-null values exist in subscriptions. Reconcile these records before retrying this migration.';
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_razorpay_payment_id
    ON subscriptions (razorpay_payment_id)
    WHERE razorpay_payment_id IS NOT NULL;
