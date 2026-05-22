-- Vendor-only auth: notifications + calendar without profiles row

ALTER TABLE notifications ADD COLUMN IF NOT EXISTS recipient_vendor_id UUID REFERENCES vendors(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_notifications_recipient_vendor ON notifications(recipient_vendor_id);

ALTER TABLE calendar_connections ADD COLUMN IF NOT EXISTS vendor_id UUID REFERENCES vendors(id) ON DELETE CASCADE;
ALTER TABLE calendar_connections ALTER COLUMN profile_id DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_calendar_connections_vendor_provider
  ON calendar_connections(vendor_id, provider)
  WHERE vendor_id IS NOT NULL;
