-- Enforce one membership per user and organization without deleting data.
-- This intentionally aborts if duplicates exist; operators must review and
-- resolve those rows explicitly before rerunning the migration.
DO $$
BEGIN
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
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_org_memberships_user_org
    ON org_memberships (user_id, org_id);
