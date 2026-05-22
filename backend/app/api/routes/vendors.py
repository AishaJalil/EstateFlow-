from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user, require_roles
from app.db import get_supabase_admin
from app.schemas import VendorCreate, VendorLogin, VendorRegister
from app.services.passwords import hash_password, verify_password
from app.services.vendor_auth import create_vendor_access_token

router = APIRouter(prefix="/vendors", tags=["vendors"])


def _public_vendor(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "passwords"}


@router.post("/register")
async def register_vendor(body: VendorRegister):
    """Vendor self-registration — stored only in vendors table (no profiles row)."""
    admin = get_supabase_admin()
    email_norm = body.email.strip().lower()

    existing = (
        admin.table("vendors")
        .select("id")
        .eq("email", email_norm)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=400, detail="A vendor with this email already exists")

    vendor_row = {
        "name": body.name.strip(),
        "specialty": body.specialty,
        "phone": body.phone.strip(),
        "email": email_norm,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "city": body.city,
        "area": body.area,
        "available": 0,
        "rating": 5.0,
        "passwords": hash_password(body.password),
    }
    ins = admin.table("vendors").insert(vendor_row).execute()
    if not ins.data:
        raise HTTPException(status_code=500, detail="Failed to create vendor account")
    row = ins.data[0]
    token = create_vendor_access_token(vendor_id=row["id"], email=email_norm)
    return {
        "data": {
            "vendor": _public_vendor(row),
            "access_token": token,
            "token_type": "bearer",
        }
    }


@router.post("/login")
async def login_vendor(body: VendorLogin):
    """Vendor sign-in — email + password checked against vendors table."""
    admin = get_supabase_admin()
    email_norm = body.email.strip().lower()
    result = (
        admin.table("vendors")
        .select("id, name, email, passwords")
        .eq("email", email_norm)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    row = result.data[0]
    if not verify_password(body.password, row.get("passwords")):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_vendor_access_token(vendor_id=row["id"], email=row.get("email") or email_norm)
    return {
        "data": {
            "vendor": _public_vendor(row),
            "access_token": token,
            "token_type": "bearer",
        }
    }


@router.get("/me")
async def vendor_me(user: dict = Depends(get_current_user)):
    if user.get("auth_type") != "vendor":
        raise HTTPException(status_code=403, detail="Vendor session required")
    admin = get_supabase_admin()
    row = (
        admin.table("vendors")
        .select("*")
        .eq("id", user["vendor_id"])
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Vendor not found")
    v = _public_vendor(row.data[0])
    return {
        "data": {
            "id": v["id"],
            "email": v.get("email"),
            "role": "vendor",
            "full_name": v.get("name"),
            "vendor_id": v["id"],
        }
    }


@router.get("")
async def list_vendors(user: dict = Depends(get_current_user)):
    admin = get_supabase_admin()
    result = admin.table("vendors").select("*").order("rating", desc=True).execute()
    return {"data": [_public_vendor(r) for r in (result.data or [])]}


@router.post("")
async def create_vendor(
    body: VendorCreate,
    user: dict = Depends(require_roles("admin", "manager")),
):
    admin = get_supabase_admin()
    payload = body.model_dump(exclude_none=True)
    if body.password:
        payload["passwords"] = hash_password(body.password)
    payload.pop("password", None)
    result = admin.table("vendors").insert(payload).execute()
    row = result.data[0] if result.data else None
    return {"data": _public_vendor(row) if row else None}
