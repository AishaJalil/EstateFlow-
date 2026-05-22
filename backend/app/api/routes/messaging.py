from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.db import get_supabase_admin
from app.services.vendor_outreach import process_vendor_reply

router = APIRouter(prefix="/messaging", tags=["messaging"])


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


def _can_access_thread(user: dict[str, Any], thread: dict[str, Any]) -> bool:
    role = user.get("role")
    if role in ("admin", "manager"):
        return True
    if role == "tenant" and thread.get("tenant_id") == user["id"]:
        return True
    if role == "vendor" and user.get("vendor_id") and thread.get("vendor_id") == user["vendor_id"]:
        return True
    return False


@router.get("/threads")
async def list_threads(user: dict = Depends(get_current_user)):
    admin = get_supabase_admin()
    role = user.get("role")

    q = admin.table("message_threads").select(
        "*, maintenance_requests(ticket_id, property_name, unit, status)"
    )
    if role == "tenant":
        q = q.eq("tenant_id", user["id"])
    elif role == "vendor":
        vid = user.get("vendor_id")
        if not vid:
            return {"data": []}
        q = q.eq("vendor_id", vid)
    elif role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = q.order("updated_at", desc=True).execute()
    return {"data": result.data or []}


@router.get("/threads/{thread_id}/messages")
async def list_messages(thread_id: str, user: dict = Depends(get_current_user)):
    admin = get_supabase_admin()
    thread = (
        admin.table("message_threads").select("*").eq("id", thread_id).limit(1).execute()
    )
    if not thread.data:
        raise HTTPException(status_code=404, detail="Thread not found")
    row = thread.data[0]
    if not _can_access_thread(user, row):
        raise HTTPException(status_code=403, detail="Access denied")

    msgs = (
        admin.table("messages")
        .select("*")
        .eq("thread_id", thread_id)
        .order("created_at", desc=False)
        .execute()
    )
    return {"data": msgs.data or [], "thread": row}


@router.post("/threads/{thread_id}/messages")
async def send_message(
    thread_id: str,
    body: MessageCreate,
    user: dict = Depends(get_current_user),
):
    admin = get_supabase_admin()
    thread = (
        admin.table("message_threads").select("*").eq("id", thread_id).limit(1).execute()
    )
    if not thread.data:
        raise HTTPException(status_code=404, detail="Thread not found")
    row = thread.data[0]
    if not _can_access_thread(user, row):
        raise HTTPException(status_code=403, detail="Access denied")

    role = user.get("role")
    if role == "tenant":
        sender_type = "tenant"
    elif role == "vendor":
        sender_type = "vendor"
    else:
        raise HTTPException(status_code=403, detail="Only tenants and vendors may reply here")

    vendor_id = row.get("vendor_id") if sender_type == "vendor" else None
    sender_profile_id = user["id"] if user.get("auth_type") != "vendor" else None
    ins = (
        admin.table("messages")
        .insert(
            {
                "thread_id": thread_id,
                "sender_type": sender_type,
                "sender_profile_id": sender_profile_id,
                "body": body.body.strip(),
                "vendor_id": vendor_id,
                "outreach_processed": False,
            }
        )
        .execute()
    )
    admin.table("message_threads").update(
        {"updated_at": datetime.utcnow().isoformat()}
    ).eq("id", thread_id).execute()

    msg = ins.data[0] if ins.data else None
    if sender_type == "vendor" and vendor_id and msg:
        await process_vendor_reply(msg["id"], thread_id, body.body.strip(), vendor_id)

    return {"data": msg}
