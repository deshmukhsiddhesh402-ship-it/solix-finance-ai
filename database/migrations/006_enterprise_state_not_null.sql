-- Align persisted enterprise state flags with database/schema.sql and ORM metadata.
-- Fail before any ALTER when legacy NULL state values exist; do not infer whether
-- a key was revoked, a report should be active, or a notification was read.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM api_keys WHERE revoked IS NULL) THEN
        RAISE EXCEPTION
            'Cannot enforce api_keys.revoked NOT NULL: legacy NULL values exist. Reconcile key state before retrying this migration.';
    END IF;

    IF EXISTS (SELECT 1 FROM scheduled_reports WHERE is_active IS NULL) THEN
        RAISE EXCEPTION
            'Cannot enforce scheduled_reports.is_active NOT NULL: legacy NULL values exist. Reconcile report state before retrying this migration.';
    END IF;

    IF EXISTS (SELECT 1 FROM notifications WHERE is_read IS NULL) THEN
        RAISE EXCEPTION
            'Cannot enforce notifications.is_read NOT NULL: legacy NULL values exist. Reconcile notification state before retrying this migration.';
    END IF;
END;
$$;

ALTER TABLE api_keys ALTER COLUMN revoked SET NOT NULL;
ALTER TABLE scheduled_reports ALTER COLUMN is_active SET NOT NULL;
ALTER TABLE notifications ALTER COLUMN is_read SET NOT NULL;
