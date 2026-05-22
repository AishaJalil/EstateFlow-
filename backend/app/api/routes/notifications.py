from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.db import get_supabase_admin

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(user: dict = Depends(get_current_user)):
    admin = get_supabase_admin()
    q = admin.table("notifications").select("*")
    if user.get("auth_type") == "vendor":
        q = q.eq("recipient_vendor_id", user["vendor_id"])
    else:
        q = q.eq("recipient_id", user["id"])
    result = q.order("created_at", desc=True).limit(50).execute()
    return {"data": result.data or []}


@router.patch("/{notification_id}/read")
async def mark_read(notification_id: str, user: dict = Depends(get_current_user)):
    admin = get_supabase_admin()
    q = admin.table("notifications").update({"status": "sent"}).eq("id", notification_id)
    if user.get("auth_type") == "vendor":
        q.eq("recipient_vendor_id", user["vendor_id"]).execute()
    else:
        q.eq("recipient_id", user["id"]).execute()
    return {"ok": True}
