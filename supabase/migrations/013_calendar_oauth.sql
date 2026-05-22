-- Per-user Google Calendar OAuth (tenants and vendors connect their own calendars).
-- profiles.vendor_id = which vendor BUSINESS this login represents (1:1), NOT "tenant's vendor".
-- Many tenants ↔ many vendors: message_threads, vendor_outreach, maintenance_requests.

CREATE TABLE IF NOT EXISTS calendar_connections (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id          UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    provider            TEXT NOT NULL DEFAULT 'google' CHECK (provider = 'google'),
    calendar_id         TEXT NOT NULL DEFAULT 'primary',
    access_token_enc    TEXT NOT NULL,
    refresh_token_enc   TEXT,
    token_expiry        TIMESTAMPTZ,
    scopes              TEXT[] DEFAULT ARRAY['https://www.googleapis.com/auth/calendar.events'],
    connected_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (profile_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_calendar_connections_profile ON calendar_connections(profile_id);

ALTER TABLE calendar_connections ENABLE ROW LEVEL SECURITY;

CREATE POLICY calendar_conn_own ON calendar_connections FOR SELECT TO authenticated
  USING (profile_id = auth.uid());

COMMENT ON COLUMN profiles.vendor_id IS
  'For role=vendor only: links this login to one row in vendors. Tenants have NULL. '
  'Multi-vendor relationships use message_threads and vendor_outreach, not this column.';
