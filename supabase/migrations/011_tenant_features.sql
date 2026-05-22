-- Migration 011: Tenant-facing features
-- 1. WhatsApp phone on profiles and vendors
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS whatsapp_phone TEXT;
ALTER TABLE vendors  ADD COLUMN IF NOT EXISTS whatsapp_phone TEXT;

-- 2. Update notifications type check to include 'whatsapp'
ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_type_check;
ALTER TABLE notifications ADD CONSTRAINT notifications_type_check
  CHECK (type IN ('sms', 'email', 'in_app', 'whatsapp'));

-- 3. Vendor ratings submitted by tenants
CREATE TABLE IF NOT EXISTS vendor_ratings (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vendor_id   UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
  request_id  UUID NOT NULL REFERENCES maintenance_requests(id) ON DELETE CASCADE,
  tenant_id   UUID REFERENCES profiles(id) ON DELETE SET NULL,
  rating      INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment     TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (vendor_id, request_id)   -- one rating per request per vendor
);

CREATE INDEX IF NOT EXISTS idx_vendor_ratings_vendor  ON vendor_ratings(vendor_id);
CREATE INDEX IF NOT EXISTS idx_vendor_ratings_tenant  ON vendor_ratings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_vendor_ratings_request ON vendor_ratings(request_id);

-- 4. Mark notifications as read
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ;

-- 5. Tenant feedback on resolved requests
ALTER TABLE maintenance_requests ADD COLUMN IF NOT EXISTS tenant_feedback TEXT;
ALTER TABLE maintenance_requests ADD COLUMN IF NOT EXISTS tenant_confirmed_resolved BOOLEAN DEFAULT FALSE;
