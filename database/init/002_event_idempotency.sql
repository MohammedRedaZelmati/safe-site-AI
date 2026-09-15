ALTER TABLE violations
    ADD COLUMN IF NOT EXISTS event_key VARCHAR(64);

ALTER TABLE violations
    DROP CONSTRAINT IF EXISTS violations_event_key_format;

ALTER TABLE violations
    ADD CONSTRAINT violations_event_key_format
    CHECK (event_key IS NULL OR event_key ~ '^[0-9a-f]{64}$');

CREATE UNIQUE INDEX IF NOT EXISTS uq_violations_event_key
    ON violations (event_key)
    WHERE event_key IS NOT NULL;
