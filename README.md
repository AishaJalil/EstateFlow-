# EstateFlow

Enterprise multi-agent property management platform (Pakistan-first). Tenants submit maintenance via the web portal; LangGraph agents classify, prioritize, match vendors (geolocation + Supabase), and schedule. Managers run inspections with AI risk assessment.

## Stack

- **Frontend:** React + Vite + TypeScript + Supabase Auth
- **Backend:** FastAPI + LangGraph + OpenRouter (Ollama fallback optional)
- **Database:** Supabase PostgreSQL + Storage

## Prerequisites

- Node.js 18+
- Python 3.11+
- Supabase project (schema applied)
- OpenRouter API key

## 1. Supabase setup

1. In [Supabase Dashboard](https://supabase.com/dashboard) → SQL Editor, run:
   - `supabase/migrations/001_initial_schema.sql` (skip tables you already have; add missing columns like `latitude`, `longitude`, `maintenance_request_media`)
   - `supabase/migrations/002_storage_and_rls.sql`
2. Create Storage bucket: **maintenance-media** (private).
3. Authentication → Providers → enable Email.
4. Copy **Project URL**, **anon key**, **service_role key**, and **JWT Secret** (Settings → API).

### If you already ran the original schema

Run only these additions in SQL Editor:

```sql
ALTER TABLE properties ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;
ALTER TABLE vendors ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE vendors ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;
ALTER TABLE vendors ADD COLUMN IF NOT EXISTS city TEXT;
ALTER TABLE vendors ADD COLUMN IF NOT EXISTS area TEXT;
ALTER TABLE maintenance_requests ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE maintenance_requests ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;
ALTER TABLE maintenance_requests DROP CONSTRAINT IF EXISTS maintenance_requests_status_check;
ALTER TABLE maintenance_requests ADD CONSTRAINT maintenance_requests_status_check
  CHECK (status IN ('Open', 'In Progress', 'Scheduled', 'Resolved', 'Pending Approval'));

CREATE TABLE IF NOT EXISTS maintenance_request_media (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id UUID NOT NULL REFERENCES maintenance_requests(id) ON DELETE CASCADE,
  storage_path TEXT NOT NULL,
  mime_type TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE maintenance_pipeline_results ADD COLUMN IF NOT EXISTS human_approved BOOLEAN DEFAULT FALSE;
```

### Seed Pakistan test data (properties, units, vendors)

Run in SQL Editor (in order):

0. **`008_add_geo_columns.sql`** — only if your DB was created from the original schema without `latitude`/`longitude`  
1. `005_seed_pakistan_data.sql` — 3 properties, 7 units, 10 named vendors  
2. `006_seed_100_vendors.sql` — **100 vendors** with geo spread across cities  
3. `007_seed_more_properties.sql` — 5 more properties + units  

(005–007 now auto-add geo columns if missing; running **008** first is still the clearest fix.)

Verify vendors: `SELECT COUNT(*) FROM vendors WHERE email LIKE 'vendor%@estateflow.pk';` → should be **100**.

### How properties work (you do NOT have to use Supabase UI)

| Role | What to do |
|------|------------|
| **Dev / quick start** | Run seed SQL above — tenants see properties in dropdown |
| **Manager / admin** | App → **Properties** → add building name, city, units (`101, 102`) |
| **Manual (optional)** | Supabase → Table Editor → `properties` + `units` |

Tenants **cannot** create properties; they only select from the list when submitting a request.

Update vendor coordinates for Karachi/Lahore tests:

```sql
UPDATE vendors SET latitude = 24.8607, longitude = 67.0011, city = 'Karachi' WHERE specialty = 'plumbing' LIMIT 1;
```

## 2. Environment files

**Environment** — copy `.env.example` to either `EstateFlow/.env` (repo root) or `backend/.env` (both work):

```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=your-jwt-secret
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free
CORS_ORIGINS=http://localhost:5173
```

**Frontend** — uses the same root `EstateFlow/.env` (must include `VITE_*` keys). Or copy `frontend/.env.example` to `frontend/.env`:

```env
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_API_URL=http://localhost:8000
```

## 3. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

## 4. Frontend

```powershell
cd frontend
npm install
npm run dev
```

App: http://localhost:5173

## 5. First users

1. Sign up as **tenant** → submit a request (Roman Urdu text + optional photo + geolocation).
2. Sign up as **manager** → open **Approvals** for Critical items.
3. **Vendors** use `/vendor/register` (separate portal) — specialty, phone, browser geolocation + city/area.
4. Tenants and vendors connect **Google Calendar** under **Calendar** (tenant) or **Calendar** (vendor portal).

### Migrations (messaging + MCP calendar)

Run in order after earlier migrations: `011_messaging_vendor_outreach.sql`, `012_auth_vendor_role.sql`, `013_calendar_oauth.sql`.

Enable Supabase **Realtime** for table `messages` (Database → Replication) so the chat UI updates live.

### Google Calendar MCP (highlight)

EstateFlow ships an MCP server at `backend/mcp_servers/estateflow_calendar/`:

| Tool | Purpose |
|------|---------|
| `calendar_connection_status` | Check if a profile connected OAuth |
| `calendar_create_event` | Book on one user's calendar |
| `calendar_book_maintenance_pair` | Book tenant + vendor calendars for a visit |
| `calendar_vendor_profile_id` | Map `vendors.id` → vendor user's `profile_id` |

**Per-user OAuth** is stored in `calendar_connections` (encrypted). The agent loads tokens only for the tenant and vendor involved in each booking — this scales to many users without one shared calendar.

**Backend `.env` additions:**

```env
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/calendar/callback
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CALENDAR_TOKEN_ENCRYPTION_KEY=...
MCP_CALENDAR_USE_STDIO=false
```

**Cursor IDE:** `.cursor/mcp.json` points at the same server for local agent tooling.

When a vendor confirms a visit, `book_maintenance_appointment` calls MCP tool `calendar_book_maintenance_pair`.

### `profiles.vendor_id` (not “one vendor per tenant”)

- **Tenants** have `vendor_id = NULL`.
- **Vendor logins** have `vendor_id` = their row in `vendors` (this account *is* that business).
- Many tenants ↔ many vendors per job: `message_threads`, `vendor_outreach`, `maintenance_requests` — not `profiles.vendor_id`.

## Maintenance agent pipeline

1. `pii_redactor` — masks CNIC/phone/email  
2. `security_scanner` — injection/spam  
3. `fraud_check` — duplicate submissions (24h)  
4. `intake_classifier` — category/urgency (OpenRouter)  
5. `governance` — compliance flags, human gate for Critical  
6. `performance_monitor` — SLA score  
7. `dispatcher` — haversine vendor match + schedule  

Results persist to `maintenance_pipeline_results` and `agent_logs`.

## Project structure

```
EstateFlow/
├── backend/app/          # FastAPI + LangGraph
├── frontend/src/         # React UI
├── supabase/migrations/  # SQL schema + RLS
└── README.md
```
