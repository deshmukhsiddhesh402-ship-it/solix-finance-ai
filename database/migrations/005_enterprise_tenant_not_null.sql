-- Enforce database-level tenant ownership for enterprise and billing rows.
-- The ORM already marks these identifiers NOT NULL. Fail before any ALTER if
-- historical orphan rows exist; reconcile them explicitly rather than guessing
-- an organization or silently deleting financial/security records.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM org_memberships
        WHERE user_id IS NULL OR org_id IS NULL
    ) THEN
        RAISE EXCEPTION
            'Cannot enforce org_memberships tenant ownership: null user_id or org_id rows exist. Reconcile them before retrying this migration.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM api_keys
        WHERE org_id IS NULL
    ) THEN
        RAISE EXCEPTION
            'Cannot enforce api_keys tenant ownership: null org_id rows exist. Reconcile them before retrying this migration.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM scheduled_reports
        WHERE org_id IS NULL
    ) THEN
        RAISE EXCEPTION
            'Cannot enforce scheduled_reports tenant ownership: null org_id rows exist. Reconcile them before retrying this migration.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM subscriptions
        WHERE org_id IS NULL
    ) THEN
        RAISE EXCEPTION
            'Cannot enforce subscriptions tenant ownership: null org_id rows exist. Reconcile them before retrying this migration.';
    END IF;
END;
$$;

ALTER TABLE org_memberships ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE org_memberships ALTER COLUMN org_id SET NOT NULL;
ALTER TABLE api_keys ALTER COLUMN org_id SET NOT NULL;
ALTER TABLE scheduled_reports ALTER COLUMN org_id SET NOT NULL;
ALTER TABLE subscriptions ALTER COLUMN org_id SET NOT NULL;
