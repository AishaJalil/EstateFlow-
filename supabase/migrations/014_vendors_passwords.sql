-- Vendor login password (bcrypt hash, not plaintext)
ALTER TABLE vendors ADD COLUMN IF NOT EXISTS passwords TEXT;

-- Default all existing vendors to bcrypt hash of '123456' (cost factor 12)
UPDATE vendors
SET passwords = '$2b$12$xcMwVHlrWbn7snujtyufI.fz1j5Qs1rzNLOA7OkXUYjapCOi3ExIi'
WHERE passwords IS NULL;

COMMENT ON COLUMN vendors.passwords IS 'bcrypt hash of vendor portal password';
