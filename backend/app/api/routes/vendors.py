from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user, require_roles
from app.db import get_supabase_admin
from app.schemas import VendorCreate, VendorRateBody

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("")
async def list_vendors(user: dict = Depends(get_current_user)):
    admin = get_supabase_admin()
    result = admin.table("vendors").select("*").order("rating", desc=True).execute()
    return {"data": result.data or []}


@router.post("")
async def create_vendor(
    body: VendorCreate,
    user: dict = Depends(require_roles("admin", "manager")),
):
    admin = get_supabase_admin()
    result = admin.table("vendors").insert(body.model_dump(exclude_none=True)).execute()
    return {"data": result.data[0] if result.data else None}


@router.post("/{vendor_id}/rate")
async def rate_vendor(
    vendor_id: str,
    body: VendorRateBody,
    user: dict = Depends(get_current_user),
):
    """Tenant submits a star rating (1-5) for a vendor after a completed request."""
    admin = get_supabase_admin()

    # Verify this vendor exists
    v = admin.table("vendors").select("id, rating, total_assignments").eq("id", vendor_id).limit(1).execute()
    if not v.data:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Find the associated request_id for this tenant + vendor combination
    req = (
        admin.table("maintenance_pipeline_results")
        .select("request_id")
        .eq("assigned_vendor_id", vendor_id)
        .execute()
    )
    request_ids = [r["request_id"] for r in (req.data or [])]

    # Find a resolved request owned by this tenant for this vendor
    matched_request_id: str | None = None
    if request_ids:
        tenant_req = (
            admin.table("maintenance_requests")
            .select("id")
            .eq("tenant_id", user["id"])
            .eq("status", "Resolved")
            .in_("id", request_ids)
            .limit(1)
            .execute()
        )
        if tenant_req.data:
            matched_request_id = tenant_req.data[0]["id"]

    if not matched_request_id:
        raise HTTPException(
            status_code=403,
            detail="You can only rate a vendor after your request has been resolved.",
        )

    # Upsert rating record
    try:
        admin.table("vendor_ratings").upsert(
            {
                "vendor_id": vendor_id,
                "request_id": matched_request_id,
                "tenant_id": user["id"],
                "rating": body.rating,
                "comment": body.comment,
            },
            on_conflict="vendor_id,request_id",
        ).execute()
    except Exception:
        # Already rated — still return 200
        pass

    # Recompute vendor average rating
    all_ratings = (
        admin.table("vendor_ratings")
        .select("rating")
        .eq("vendor_id", vendor_id)
        .execute()
    )
    if all_ratings.data:
        avg = sum(r["rating"] for r in all_ratings.data) / len(all_ratings.data)
        admin.table("vendors").update({"rating": round(avg, 1)}).eq("id", vendor_id).execute()

    return {"message": "Rating submitted. Thank you!", "new_avg": round(avg if all_ratings.data else body.rating, 1)}
