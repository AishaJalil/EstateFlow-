"""Notifications API routes — tenant inbox, mark-as-read."""
from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.db import get_supabase_admin

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(user: dict = Depends(get_current_user)):
    """Return all notifications for the current user, newest first."""
    admin = get_supabase_admin()
    result = (
        admin.table("notifications")
        .select("*")
        .eq("recipient_id", user["id"])
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    rows = result.data or []
    unread = sum(1 for r in rows if not r.get("read_at"))
    return {"data": rows, "unread_count": unread}


@router.patch("/{notification_id}/read")
async def mark_read(notification_id: str, user: dict = Depends(get_current_user)):
    """Mark a single notification as read."""
    admin = get_supabase_admin()
    from datetime import datetime

    admin.table("notifications").update(
        {"read_at": datetime.utcnow().isoformat()}
    ).eq("id", notification_id).eq("recipient_id", user["id"]).execute()
    return {"ok": True}


@router.patch("/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    """Mark all of the current user's notifications as read."""
    admin = get_supabase_admin()
    from datetime import datetime

    admin.table("notifications").update(
        {"read_at": datetime.utcnow().isoformat()}
    ).eq("recipient_id", user["id"]).is_("read_at", "null").execute()
    return {"ok": True}
