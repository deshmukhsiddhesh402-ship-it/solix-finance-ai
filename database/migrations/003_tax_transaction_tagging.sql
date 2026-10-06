-- Solix Finance AI — additive GST/TDS transaction tagging
-- Safe rollout: metadata-only columns, no destructive operations, no data rewrite.
-- Execute manually after reviewing existing production data and backups.

ALTER TABLE journal_lines
    ADD COLUMN IF NOT EXISTS gst_rate_pct NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS gst_type VARCHAR(10),
    ADD COLUMN IF NOT EXISTS gst_taxable_value NUMERIC(18,2),
    ADD COLUMN IF NOT EXISTS tds_section VARCHAR(10),
    ADD COLUMN IF NOT EXISTS tds_rate NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS tds_amount NUMERIC(18,2);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'journal_lines_gst_rate_pct_range'
    ) THEN
        ALTER TABLE journal_lines ADD CONSTRAINT journal_lines_gst_rate_pct_range
            CHECK (gst_rate_pct IS NULL OR (gst_rate_pct >= 0 AND gst_rate_pct <= 100));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'journal_lines_gst_type_allowed'
    ) THEN
        ALTER TABLE journal_lines ADD CONSTRAINT journal_lines_gst_type_allowed
            CHECK (gst_type IS NULL OR gst_type IN ('IGST', 'CGST', 'SGST', 'NONE'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'journal_lines_tds_rate_range'
    ) THEN
        ALTER TABLE journal_lines ADD CONSTRAINT journal_lines_tds_rate_range
            CHECK (tds_rate IS NULL OR (tds_rate >= 0 AND tds_rate <= 100));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'journal_lines_tax_amounts_nonnegative'
    ) THEN
        ALTER TABLE journal_lines ADD CONSTRAINT journal_lines_tax_amounts_nonnegative
            CHECK ((gst_taxable_value IS NULL OR gst_taxable_value >= 0) AND (tds_amount IS NULL OR tds_amount >= 0));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_journal_lines_gst_tag ON journal_lines(gst_type, gst_rate_pct);
CREATE INDEX IF NOT EXISTS idx_journal_lines_tds_tag ON journal_lines(tds_section, tds_rate);
