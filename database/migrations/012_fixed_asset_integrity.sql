-- Solix Finance AI — enforce fixed asset tenant ownership and financial invariants.
-- Existing invalid rows are not repaired automatically; reconcile them from source
-- documents and obtain accounting review before applying this migration.
-- Do not run automatically in production.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM fixed_assets WHERE org_id IS NULL) THEN
        RAISE EXCEPTION 'Cannot enforce fixed asset tenant ownership: NULL org_id rows exist.';
    END IF;
    IF EXISTS (SELECT 1 FROM fixed_assets WHERE cost < 0 OR salvage_value < 0 OR salvage_value > cost) THEN
        RAISE EXCEPTION 'Cannot constrain fixed asset values: negative or inconsistent cost/salvage rows exist.';
    END IF;
    IF EXISTS (SELECT 1 FROM fixed_assets WHERE useful_life_years <= 0) THEN
        RAISE EXCEPTION 'Cannot constrain fixed asset useful life: non-positive legacy values exist.';
    END IF;
    IF EXISTS (SELECT 1 FROM fixed_assets WHERE depreciation_method NOT IN ('straight_line', 'wdv')) THEN
        RAISE EXCEPTION 'Cannot constrain fixed asset depreciation method: unsupported legacy values exist.';
    END IF;
    IF EXISTS (SELECT 1 FROM fixed_assets WHERE length(trim(asset_name)) = 0) THEN
        RAISE EXCEPTION 'Cannot constrain fixed asset name: blank legacy names exist.';
    END IF;
END
$$;

ALTER TABLE fixed_assets
    ALTER COLUMN org_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'fixed_assets'::regclass AND conname = 'ck_fixed_asset_cost_nonnegative') THEN
        ALTER TABLE fixed_assets ADD CONSTRAINT ck_fixed_asset_cost_nonnegative CHECK (cost >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'fixed_assets'::regclass AND conname = 'ck_fixed_asset_salvage_nonnegative') THEN
        ALTER TABLE fixed_assets ADD CONSTRAINT ck_fixed_asset_salvage_nonnegative CHECK (salvage_value >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'fixed_assets'::regclass AND conname = 'ck_fixed_asset_salvage_not_above_cost') THEN
        ALTER TABLE fixed_assets ADD CONSTRAINT ck_fixed_asset_salvage_not_above_cost CHECK (salvage_value <= cost);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'fixed_assets'::regclass AND conname = 'ck_fixed_asset_useful_life_positive') THEN
        ALTER TABLE fixed_assets ADD CONSTRAINT ck_fixed_asset_useful_life_positive CHECK (useful_life_years > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'fixed_assets'::regclass AND conname = 'ck_fixed_asset_depreciation_method') THEN
        ALTER TABLE fixed_assets ADD CONSTRAINT ck_fixed_asset_depreciation_method CHECK (depreciation_method IN ('straight_line', 'wdv'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'fixed_assets'::regclass AND conname = 'ck_fixed_asset_name_nonblank') THEN
        ALTER TABLE fixed_assets ADD CONSTRAINT ck_fixed_asset_name_nonblank CHECK (length(trim(asset_name)) > 0);
    END IF;
END
$$;
