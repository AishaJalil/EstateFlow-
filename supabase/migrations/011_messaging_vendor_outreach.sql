-- Messaging, vendor outreach workflow, available as active-booking count (max 5)

-- Convert vendors.available from boolean to integer (active bookings; cap at 5)
ALTER TABLE vendors ADD COLUMN IF NOT EXISTS available_int INT DEFAULT 0;
UPDATE vendors SET available_int = CASE WHEN available IS TRUE THEN 0 ELSE 5 END;
ALTER TABLE vendors DROP COLUMN IF EXISTS available;
ALTER TABLE vendors RENAME COLUMN available_int TO available;
ALTER TABLE vendors ALTER COLUMN available SET DEFAULT 0;

-- Vendor role + link profile to vendor directory row
ALTER TABLE profiles DROP CONSTRAINT IF EXISTS profiles_role_check;
ALTER TABLE profiles ADD CONSTRAINT profiles_role_check
  CHECK (role IN ('admin', 'manager', 'inspector', 'tenant', 'vendor'));
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS vendor_id UUID REFERENCES vendors(id) ON DELETE SET NULL;

-- Awaiting vendor confirmation status
ALTER TABLE maintenance_requests DROP CONSTRAINT IF EXISTS maintenance_requests_status_check;
ALTER TABLE maintenance_requests ADD CONSTRAINT maintenance_requests_status_check
  CHECK (status IN (
    'Open', 'In Progress', 'Scheduled', 'Resolved',
    'Pending Approval', 'Blocked', 'Awaiting Vendor'
  ));

-- Ranked vendor queue + outreach state per maintenance request
CREATE TABLE IF NOT EXISTS vendor_outreach (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id          UUID NOT NULL REFERENCES maintenance_requests(id) ON DELETE CASCADE,
    ranked_vendor_ids   JSONB NOT NULL DEFAULT '[]',
    current_index       INT NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'seeking'
                            CHECK (status IN ('seeking', 'confirmed', 'exhausted', 'cancelled')),
    current_vendor_id   UUID REFERENCES vendors(id) ON DELETE SET NULL,
    response_deadline   TIMESTAMPTZ,
    confirmed_vendor_id UUID REFERENCES vendors(id) ON DELETE SET NULL,
    confirmed_at        TIMESTAMPTZ,
    scheduled_time      TIMESTAMPTZ,
    calendar_event_ids  JSONB DEFAULT '[]',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (request_id)
);

-- In-app message threads (tenant account; vendor participates on linked profile)
CREATE TABLE IF NOT EXISTS message_threads (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    maintenance_request_id  UUID NOT NULL REFERENCES maintenance_requests(id) ON DELETE CASCADE,
    tenant_id               UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    vendor_id               UUID REFERENCES vendors(id) ON DELETE SET NULL,
    status                  TEXT NOT NULL DEFAULT 'active'
                                CHECK (status IN ('active', 'closed')),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id           UUID NOT NULL REFERENCES message_threads(id) ON DELETE CASCADE,
    sender_type         TEXT NOT NULL CHECK (sender_type IN ('agent', 'tenant', 'vendor')),
    sender_profile_id   UUID REFERENCES profiles(id) ON DELETE SET NULL,
    body                TEXT NOT NULL,
    vendor_id           UUID REFERENCES vendors(id) ON DELETE SET NULL,
    outreach_processed  BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_thread_created ON messages(thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_vendor_outreach_deadline ON vendor_outreach(response_deadline)
  WHERE status = 'seeking';
CREATE INDEX IF NOT EXISTS idx_message_threads_tenant ON message_threads(tenant_id);
CREATE INDEX IF NOT EXISTS idx_message_threads_vendor ON message_threads(vendor_id);

ALTER TABLE vendor_outreach ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY vendor_outreach_read ON vendor_outreach FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM maintenance_requests mr
      WHERE mr.id = vendor_outreach.request_id
        AND (
          mr.tenant_id = auth.uid()
          OR EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role IN ('admin', 'manager'))
          OR EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.vendor_id = vendor_outreach.current_vendor_id)
        )
    )
  );

CREATE POLICY message_threads_participant ON message_threads FOR SELECT TO authenticated
  USING (
    tenant_id = auth.uid()
    OR vendor_id IN (SELECT vendor_id FROM profiles WHERE id = auth.uid() AND vendor_id IS NOT NULL)
    OR EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role IN ('admin', 'manager'))
  );

CREATE POLICY messages_thread_participant ON messages FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM message_threads t
      WHERE t.id = messages.thread_id
        AND (
          t.tenant_id = auth.uid()
          OR t.vendor_id IN (SELECT vendor_id FROM profiles p WHERE p.id = auth.uid())
          OR EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role IN ('admin', 'manager'))
        )
    )
  );

-- Tenants and vendors may send messages in their threads (backend also uses service role)
CREATE POLICY messages_insert_participant ON messages FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM message_threads t
      WHERE t.id = messages.thread_id
        AND (
          (messages.sender_type = 'tenant' AND t.tenant_id = auth.uid())
          OR (
            messages.sender_type = 'vendor'
            AND t.vendor_id IN (SELECT vendor_id FROM profiles p WHERE p.id = auth.uid())
          )
        )
    )
  );
