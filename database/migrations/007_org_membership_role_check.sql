-- Keep organization membership roles within the RBAC engine's supported set.
-- Do not rewrite unexpected historical roles: stop and require an explicit,
-- human-reviewed role reconciliation before adding the database constraint.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM org_memberships
        WHERE role IS NULL
           OR role NOT IN ('admin', 'accountant', 'auditor')
    ) THEN
        RAISE EXCEPTION
            'Cannot enforce org_memberships.role: unsupported or NULL roles exist. Reconcile each membership role before retrying this migration.';
    END IF;
END;
$$;

ALTER TABLE org_memberships
    ADD CONSTRAINT ck_org_memberships_role
    CHECK (role IN ('admin', 'accountant', 'auditor'));
