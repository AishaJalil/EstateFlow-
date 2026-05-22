from datetime import datetime, timedelta
from typing import Any

from app.db import get_supabase_admin


async def notify_in_app(
    *,
    recipient_id: str | None,
    message: str,
    subject: str | None = None,
    reference_type: str,
    reference_id: str,
    recipient_email: str | None = None,
    recipient_vendor_id: str | None = None,
) -> None:
    admin = get_supabase_admin()
    admin.table("notifications").insert(
        {
            "type": "in_app",
            "recipient_id": recipient_id,
            "recipient_vendor_id": recipient_vendor_id,
            "recipient_email": recipient_email,
            "subject": subject,
            "message": message,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "status": "sent",
            "sent_at": datetime.utcnow().isoformat(),
        }
    ).execute()


async def notify_managers_for_urgent(
    property_id: str | None,
    ticket_id: str,
    request_id: str,
    summary: str,
) -> int:
    """Notify all managers/admins (in_app). Returns count notified."""
    admin = get_supabase_admin()
    managers = (
        admin.table("profiles")
        .select("id, full_name")
        .in_("role", ["admin", "manager"])
        .execute()
    )
    count = 0
    msg = f"URGENT maintenance {ticket_id}: {summary}"
    if property_id:
        msg += f" (property {property_id})"
    for m in managers.data or []:
        await notify_in_app(
            recipient_id=m["id"],
            message=msg,
            subject=f"Urgent: {ticket_id}",
            reference_type="maintenance_request",
            reference_id=request_id,
        )
        count += 1
    return count


def schedule_follow_up_iso(hours: int = 24) -> str:
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat()
