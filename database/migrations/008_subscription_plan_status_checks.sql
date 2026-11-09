-- Restrict subscription entitlement and lifecycle values to supported states.
-- This prevents invalid plan strings from falling through to trial defaults and
-- invalid status strings from bypassing lifecycle assumptions. Existing values
-- are checked first; this migration never rewrites billing records.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM subscriptions
        WHERE plan IS NULL
           OR plan NOT IN ('trial', 'pro', 'enterprise')
    ) THEN
        RAISE EXCEPTION
            'Cannot enforce subscriptions.plan: unsupported or NULL plan values exist. Reconcile them before retrying this migration.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM subscriptions
        WHERE status IS NULL
           OR status NOT IN ('active', 'past_due', 'cancelled')
    ) THEN
        RAISE EXCEPTION
            'Cannot enforce subscriptions.status: unsupported or NULL status values exist. Reconcile them before retrying this migration.';
    END IF;
END;
$$;

ALTER TABLE subscriptions
    ADD CONSTRAINT ck_subscriptions_plan
    CHECK (plan IN ('trial', 'pro', 'enterprise'));

ALTER TABLE subscriptions
    ADD CONSTRAINT ck_subscriptions_status
    CHECK (status IN ('active', 'past_due', 'cancelled'));
