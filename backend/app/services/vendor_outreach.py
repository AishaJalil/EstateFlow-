"""Vendor outreach: message queue, 24h timeout, reply handling, calendar + notifications."""

import logging
from datetime import datetime, timedelta
from typing import Any

from app.db import get_supabase_admin
from app.services.google_calendar import book_maintenance_appointment
from app.services.notifications_helper import notify_in_app
from app.services.vendor_matching import MAX_ACTIVE_BOOKINGS
from app.services.vendor_reply_parser import parse_vendor_reply

logger = logging.getLogger(__name__)

OUTREACH_HOURS = 24


def _deadline_iso() -> str:
    return (datetime.utcnow() + timedelta(hours=OUTREACH_HOURS)).isoformat()


async def _agent_message(
    admin: Any,
    *,
    thread_id: str,
    body: str,
    vendor_id: str | None,
) -> None:
    admin.table("messages").insert(
        {
            "thread_id": thread_id,
            "sender_type": "agent",
            "body": body,
            "vendor_id": vendor_id,
            "outreach_processed": True,
        }
    ).execute()
    admin.table("message_threads").update(
        {"updated_at": datetime.utcnow().isoformat()}
    ).eq("id", thread_id).execute()


def _complaint_outreach_body(state: dict[str, Any], vendor_name: str) -> str:
    summary = state.get("summary") or state.get("redacted_issue") or "Maintenance request"
    urgency = state.get("urgency", "Medium")
    trade = state.get("vendor_specialty") or state.get("trade") or "general"
    loc = state.get("location_detail") or ""
    loc_line = f"\nLocation detail: {loc}" if loc else ""
    return (
        f"Hello {vendor_name},\n\n"
        f"EstateFlow is reaching out on behalf of the tenant regarding a {urgency} "
        f"{trade} issue:\n{summary}{loc_line}\n\n"
        "Please reply within 24 hours with:\n"
        "• Your available day and time for a visit, OR\n"
        "• That you are not available.\n\n"
        "Thank you."
    )


async def start_vendor_outreach(
    state: dict[str, Any],
    ranked_vendors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist ranked queue, open thread, message first vendor."""
    admin = get_supabase_admin()
    request_id = state["request_id"]
    tenant_id = state.get("tenant_id")
    if not tenant_id or not ranked_vendors:
        return {"outreach_started": False, "reason": "no_tenant_or_vendors"}

    vendor_ids = [v["id"] for v in ranked_vendors if v.get("id")]
    first = ranked_vendors[0]
    first_id = first.get("id")

    existing = (
        admin.table("vendor_outreach")
        .select("id")
        .eq("request_id", request_id)
        .limit(1)
        .execute()
    )
    outreach_row = {
        "request_id": request_id,
        "ranked_vendor_ids": vendor_ids,
        "current_index": 0,
        "status": "seeking",
        "current_vendor_id": first_id,
        "response_deadline": _deadline_iso(),
    }
    if existing.data:
        admin.table("vendor_outreach").update(outreach_row).eq("request_id", request_id).execute()
    else:
        admin.table("vendor_outreach").insert(outreach_row).execute()

    thread_q = (
        admin.table("message_threads")
        .select("id")
        .eq("maintenance_request_id", request_id)
        .limit(1)
        .execute()
    )
    if thread_q.data:
        thread_id = thread_q.data[0]["id"]
        admin.table("message_threads").update(
            {"vendor_id": first_id, "updated_at": datetime.utcnow().isoformat()}
        ).eq("id", thread_id).execute()
    else:
        ins = (
            admin.table("message_threads")
            .insert(
                {
                    "maintenance_request_id": request_id,
                    "tenant_id": tenant_id,
                    "vendor_id": first_id,
                    "status": "active",
                }
            )
            .execute()
        )
        thread_id = ins.data[0]["id"]

    body = _complaint_outreach_body(state, first.get("name", "Vendor"))
    await _agent_message(admin, thread_id=thread_id, body=body, vendor_id=first_id)

    admin.table("maintenance_requests").update({"status": "Awaiting Vendor"}).eq(
        "id", request_id
    ).execute()

    if first_id:
        await notify_in_app(
            recipient_vendor_id=first_id,
            recipient_id=None,
            subject="New maintenance job request",
            message=f"You have a new job inquiry: {state.get('summary', 'Maintenance')}. Reply in Messages within 24h.",
            reference_type="maintenance_request",
            reference_id=request_id,
        )

    await notify_in_app(
        recipient_id=tenant_id,
        subject="Vendor contacted",
        message=(
            f"We've contacted {first.get('name', 'a vendor')} about your issue. "
            "You'll be notified when a visit is scheduled."
        ),
        reference_type="maintenance_request",
        reference_id=request_id,
    )

    return {
        "outreach_started": True,
        "thread_id": thread_id,
        "current_vendor_id": first_id,
        "current_vendor_name": first.get("name"),
        "ranked_vendor_count": len(vendor_ids),
    }


async def _confirm_vendor(
    admin: Any,
    *,
    outreach: dict[str, Any],
    vendor_id: str,
    scheduled_iso: str | None,
    request_id: str,
    state_row: dict[str, Any] | None,
) -> None:
    vendor = (
        admin.table("vendors").select("*").eq("id", vendor_id).limit(1).execute()
    )
    vdata = vendor.data[0] if vendor.data else {}
    tenant_id = state_row.get("tenant_id") if state_row else None

    req = (
        admin.table("maintenance_requests")
        .select("ticket_id, property_name, unit, tenant_id")
        .eq("id", request_id)
        .limit(1)
        .execute()
    )
    req_data = req.data[0] if req.data else {}
    tenant_id = tenant_id or req_data.get("tenant_id")
    summary = (
        (state_row or {}).get("summary")
        or req_data.get("property_name", "")
        + " maintenance"
    )

    tenant_email = None
    if tenant_id:
        try:
            tu = admin.auth.admin.get_user_by_id(tenant_id)
            if tu and tu.user:
                tenant_email = tu.user.email
        except Exception:
            tenant_email = None

    cal = await book_maintenance_appointment(
        summary=f"EstateFlow: {summary}",
        scheduled_iso=scheduled_iso,
        tenant_email=tenant_email,
        vendor_email=vdata.get("email"),
        request_id=request_id,
        tenant_profile_id=tenant_id,
        vendor_id=vendor_id,
    )
    scheduled_display = cal.get("start", scheduled_iso)

    active = int(vdata.get("available") or 0)
    if active < MAX_ACTIVE_BOOKINGS:
        admin.table("vendors").update({"available": active + 1}).eq("id", vendor_id).execute()

    total = (vdata.get("total_assignments") or 0) + 1
    admin.table("vendors").update({"total_assignments": total}).eq("id", vendor_id).execute()

    admin.table("vendor_outreach").update(
        {
            "status": "confirmed",
            "confirmed_vendor_id": vendor_id,
            "confirmed_at": datetime.utcnow().isoformat(),
            "scheduled_time": scheduled_display,
            "calendar_event_ids": [
                e
                for e in (cal.get("tenant_event_id"), cal.get("vendor_event_id"))
                if e
            ],
            "response_deadline": None,
        }
    ).eq("id", outreach["id"]).execute()

    pl_update = {
        "assigned_vendor": vdata.get("name"),
        "assigned_vendor_id": vendor_id,
        "scheduled_time": str(scheduled_display),
    }
    admin.table("maintenance_pipeline_results").update(pl_update).eq(
        "request_id", request_id
    ).execute()

    admin.table("maintenance_requests").update({"status": "Scheduled"}).eq(
        "id", request_id
    ).execute()

    thread = (
        admin.table("message_threads")
        .select("id")
        .eq("maintenance_request_id", request_id)
        .limit(1)
        .execute()
    )
    if thread.data:
        await _agent_message(
            admin,
            thread_id=thread.data[0]["id"],
            body=(
                f"Visit confirmed with {vdata.get('name', 'vendor')} "
                f"for {scheduled_display}. Calendar updated."
            ),
            vendor_id=vendor_id,
        )

    if tenant_id:
        await notify_in_app(
            recipient_id=tenant_id,
            subject="Visit scheduled",
            message=f"Your maintenance visit is scheduled for {scheduled_display}.",
            reference_type="maintenance_request",
            reference_id=request_id,
        )
    await notify_in_app(
        recipient_vendor_id=vendor_id,
        recipient_id=None,
        subject="Visit scheduled",
        message=f"You are scheduled for {scheduled_display}.",
        reference_type="maintenance_request",
        reference_id=request_id,
    )


async def _contact_next_vendor(
    admin: Any,
    *,
    outreach: dict[str, Any],
    request_id: str,
    state_hint: dict[str, Any] | None,
) -> bool:
    ranked: list[str] = outreach.get("ranked_vendor_ids") or []
    nxt = (outreach.get("current_index") or 0) + 1
    if nxt >= len(ranked):
        admin.table("vendor_outreach").update({"status": "exhausted"}).eq(
            "id", outreach["id"]
        ).execute()
        admin.table("maintenance_requests").update({"status": "In Progress"}).eq(
            "id", request_id
        ).execute()
        tenant_id = state_hint.get("tenant_id") if state_hint else None
        if tenant_id:
            await notify_in_app(
                recipient_id=tenant_id,
                subject="Vendor search update",
                message=(
                    "We could not confirm a vendor within the outreach window. "
                    "A property manager will follow up."
                ),
                reference_type="maintenance_request",
                reference_id=request_id,
            )
        return False

    vendor_id = ranked[nxt]
    v = admin.table("vendors").select("name").eq("id", vendor_id).limit(1).execute()
    name = v.data[0]["name"] if v.data else "Vendor"

    admin.table("vendor_outreach").update(
        {
            "current_index": nxt,
            "current_vendor_id": vendor_id,
            "response_deadline": _deadline_iso(),
            "status": "seeking",
        }
    ).eq("id", outreach["id"]).execute()

    thread = (
        admin.table("message_threads")
        .select("id")
        .eq("maintenance_request_id", request_id)
        .limit(1)
        .execute()
    )
    if not thread.data:
        return True

    thread_id = thread.data[0]["id"]
    admin.table("message_threads").update({"vendor_id": vendor_id}).eq("id", thread_id).execute()

    body = _complaint_outreach_body(state_hint or {}, name)
    await _agent_message(admin, thread_id=thread_id, body=body, vendor_id=vendor_id)

    await notify_in_app(
        recipient_vendor_id=vendor_id,
        recipient_id=None,
        subject="New maintenance job request",
        message=f"New job inquiry (backup vendor). Reply in Messages within 24h.",
        reference_type="maintenance_request",
        reference_id=request_id,
    )
    return True


async def process_vendor_reply(message_id: str, thread_id: str, body: str, vendor_id: str) -> None:
    admin = get_supabase_admin()
    thread = (
        admin.table("message_threads")
        .select("maintenance_request_id, tenant_id")
        .eq("id", thread_id)
        .limit(1)
        .execute()
    )
    if not thread.data:
        return
    request_id = thread.data[0]["maintenance_request_id"]

    outreach_q = (
        admin.table("vendor_outreach")
        .select("*")
        .eq("request_id", request_id)
        .eq("status", "seeking")
        .limit(1)
        .execute()
    )
    if not outreach_q.data:
        return
    outreach = outreach_q.data[0]
    if outreach.get("current_vendor_id") != vendor_id:
        return

    admin.table("messages").update({"outreach_processed": True}).eq("id", message_id).execute()

    parsed = await parse_vendor_reply(body)
    pl = (
        admin.table("maintenance_pipeline_results")
        .select("summary, urgency, vendor_specialty")
        .eq("request_id", request_id)
        .limit(1)
        .execute()
    )
    state_hint = {
        "summary": pl.data[0].get("summary") if pl.data else None,
        "urgency": pl.data[0].get("urgency") if pl.data else "Medium",
        "vendor_specialty": pl.data[0].get("vendor_specialty") if pl.data else "general",
        "tenant_id": thread.data[0].get("tenant_id"),
    }

    if parsed["intent"] == "accept":
        await _confirm_vendor(
            admin,
            outreach=outreach,
            vendor_id=vendor_id,
            scheduled_iso=parsed.get("scheduled_iso"),
            request_id=request_id,
            state_row=state_hint,
        )
        return

    if parsed["intent"] == "decline":
        await _contact_next_vendor(
            admin, outreach=outreach, request_id=request_id, state_hint=state_hint
        )
        return


async def process_outreach_timeouts() -> int:
    """Advance to next vendor when 24h deadline passes without confirmation."""
    admin = get_supabase_admin()
    now = datetime.utcnow().isoformat()
    due = (
        admin.table("vendor_outreach")
        .select("*")
        .eq("status", "seeking")
        .lt("response_deadline", now)
        .execute()
    )
    count = 0
    for outreach in due.data or []:
        request_id = outreach["request_id"]
        pl = (
            admin.table("maintenance_pipeline_results")
            .select("summary, urgency, vendor_specialty")
            .eq("request_id", request_id)
            .limit(1)
            .execute()
        )
        mr = (
            admin.table("maintenance_requests")
            .select("tenant_id")
            .eq("id", request_id)
            .limit(1)
            .execute()
        )
        state_hint = {
            "summary": pl.data[0].get("summary") if pl.data else None,
            "urgency": pl.data[0].get("urgency") if pl.data else "Medium",
            "vendor_specialty": pl.data[0].get("vendor_specialty") if pl.data else "general",
            "tenant_id": mr.data[0].get("tenant_id") if mr.data else None,
        }
        thread = (
            admin.table("message_threads")
            .select("id")
            .eq("maintenance_request_id", request_id)
            .limit(1)
            .execute()
        )
        if thread.data:
            await _agent_message(
                admin,
                thread_id=thread.data[0]["id"],
                body="No response within 24 hours — contacting the next available vendor.",
                vendor_id=outreach.get("current_vendor_id"),
            )
        await _contact_next_vendor(
            admin, outreach=outreach, request_id=request_id, state_hint=state_hint
        )
        count += 1
    return count


async def process_pending_vendor_messages() -> int:
    """Parse unprocessed vendor replies in active outreach threads."""
    admin = get_supabase_admin()
    seeking = (
        admin.table("vendor_outreach")
        .select("request_id, current_vendor_id")
        .eq("status", "seeking")
        .execute()
    )
    if not seeking.data:
        return 0

    request_ids = [r["request_id"] for r in seeking.data]
    threads = (
        admin.table("message_threads")
        .select("id, maintenance_request_id")
        .in_("maintenance_request_id", request_ids)
        .execute()
    )
    thread_by_req = {t["maintenance_request_id"]: t["id"] for t in threads.data or []}
    vendor_by_req = {r["request_id"]: r["current_vendor_id"] for r in seeking.data}

    count = 0
    for req_id, thread_id in thread_by_req.items():
        vendor_id = vendor_by_req.get(req_id)
        if not vendor_id:
            continue
        msgs = (
            admin.table("messages")
            .select("id, body")
            .eq("thread_id", thread_id)
            .eq("sender_type", "vendor")
            .eq("outreach_processed", False)
            .order("created_at", desc=False)
            .execute()
        )
        for msg in msgs.data or []:
            await process_vendor_reply(msg["id"], thread_id, msg["body"], vendor_id)
            count += 1
    return count
