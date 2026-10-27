-- Enforce one membership per user and organization without deleting data.
-- This intentionally aborts if duplicates exist; operators must review and
-- resolve those rows explicitly before rerunning the migration.
DO $migration$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM org_memberships
        WHERE user_id IS NULL OR org_id IS NULL
    ) THEN
        RAISE EXCEPTION
            'Null org_memberships keys found; review and resolve these rows before applying migration 004.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM org_memberships
        GROUP BY user_id, org_id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Duplicate org_memberships found; review and resolve duplicates before applying migration 004.';
    END IF;
END
$migration$;

ALTER TABLE org_memberships
    ALTER COLUMN user_id SET NOT NULL,
    ALTER COLUMN org_id SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_org_memberships_user_org
    ON org_memberships (user_id, org_id);
