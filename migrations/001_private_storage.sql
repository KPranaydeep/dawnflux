-- Run once in Neon SQL Editor as the database administrator.
-- The application role needs only SELECT/INSERT/UPDATE on these tables.
CREATE TABLE IF NOT EXISTS dawnflux_owners (
    owner_id TEXT PRIMARY KEY,
    settings JSONB NOT NULL,
    revision BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS dawnflux_records (
    owner_id TEXT NOT NULL REFERENCES dawnflux_owners(owner_id),
    kind TEXT NOT NULL CHECK (kind IN ('light', 'sleep')),
    record_key TEXT NOT NULL,
    payload JSONB NOT NULL,
    PRIMARY KEY (owner_id, kind, record_key)
);
REVOKE ALL ON dawnflux_owners, dawnflux_records FROM PUBLIC;
