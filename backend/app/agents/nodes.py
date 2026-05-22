import re
import time
from datetime import datetime, timedelta
from typing import Any

from app.agents.progress import persist_agent_step
from app.agents.state import MaintenanceGraphState
from app.config import get_settings
from app.db import get_supabase_admin
from app.services.external_vendor_search import search_external_vendor
from app.services.issue_parser import parse_urgency_fast
from app.services.llm import structured_completion
from app.services.notifications_helper import (
    notify_in_app,
    notify_managers_for_urgent,
    schedule_follow_up_iso,
)
from app.services.report_generator import (
    build_audit_ledger,
    build_report_summary,
    render_maintenance_pdf,
    upload_report_pdf,
)
from app.services.risk_matrix import SLA_BY_URGENCY, lookup_risk_hits
from app.services.vendor_matching import rank_vendors
from app.services.whatsapp import send_whatsapp, send_whatsapp_to_managers

PII_PATTERNS = [
    (r"\b\d{5}-\d{7}-\d\b", "cnic"),
    (r"\b03\d{2}[-\s]?\d{7}\b", "phone_pk"),
    (r"\b\+?92\d{10,12}\b", "phone"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "email"),
    (r"\b(gate\s*code|access\s*code|pin)\s*[:#]?\s*\w+", "gate_code"),
]

INJECTION_MARKERS = ["ignore previous", "system prompt", "jailbreak", "<script", "drop table"]


def _pop_llm_tokens(parsed: dict[str, Any], state: MaintenanceGraphState) -> tuple[dict[str, Any], int]:
    tokens = int(parsed.pop("__llm_tokens", 0) or 0)
    return parsed, state.get("llm_tokens_estimated", 0) + tokens


async def _track(state: MaintenanceGraphState, agent: str, output: dict, ms: int) -> MaintenanceGraphState:
    timings = {**state.get("node_timings_ms", {}), agent: ms}
    new_state: MaintenanceGraphState = {
        **state,
        "agents_run": [*state.get("agents_run", []), agent],
        "agent_outputs": {**state.get("agent_outputs", {}), agent: output},
        "node_timings_ms": timings,
    }
    await persist_agent_step(new_state, agent, output, ms)
    return new_state


def _redact_pii(text: str) -> tuple[str, bool, str]:
    found: list[str] = []
    redacted = text
    for pattern, label in PII_PATTERNS:
        if re.search(pattern, redacted, re.IGNORECASE):
            found.append(label)
            redacted = re.sub(pattern, f"[REDACTED_{label.upper()}]", redacted, flags=re.IGNORECASE)
    return redacted, bool(found), ", ".join(found) if found else ""


# ─── Phase 1: Ingestion & Gatekeeping ───────────────────────────────────────


async def security_agent(state: MaintenanceGraphState) -> MaintenanceGraphState:
    """Node 0: RBAC, prompt injection, PII redaction, duplicate detection."""
    start = time.perf_counter()
    admin = get_supabase_admin()
    tenant_id = state.get("tenant_id")
    property_id = state.get("property_id")

    rbac_ok = True
    rbac_notes = "Tenant context verified."
    if tenant_id:
        profile = (
            admin.table("profiles")
            .select("id, role, property_id")
            .eq("id", tenant_id)
            .limit(1)
            .execute()
        )
        row = (profile.data or [None])[0]
        if not row:
            rbac_ok = False
            rbac_notes = "Tenant profile not found."
        elif row.get("role") != "tenant" and row.get("role") not in ("admin", "manager"):
            rbac_ok = False
            rbac_notes = f"Invalid role for maintenance submit: {row.get('role')}"
        elif row.get("property_id") and property_id and str(row["property_id"]) != str(property_id):
            rbac_ok = False
            rbac_notes = "Tenant not linked to submitted property."

    text = state.get("original_issue", "")
    redacted, pii_found, pii_log = _redact_pii(text)
    lower = redacted.lower()
    threat = "none"
    is_safe = rbac_ok
    security_notes = rbac_notes

    for marker in INJECTION_MARKERS:
        if marker in lower:
            threat = "injection"
            is_safe = False
            security_notes = f"Prompt injection marker: {marker}"
            break

    duplicate = False
    if tenant_id and text:
        since = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        rows = (
            admin.table("maintenance_requests")
            .select("id, original_issue")
            .eq("tenant_id", tenant_id)
            .gte("created_at", since)
            .neq("id", state.get("request_id", ""))
            .execute()
        )
        issue_norm = text.strip().lower()
        for row in rows.data or []:
            prior = (row.get("original_issue") or "").strip().lower()
            if prior == issue_norm:
                duplicate = True
                break

    ms = int((time.perf_counter() - start) * 1000)
    output = {
        "rbac_verified": rbac_ok,
        "pii_found": pii_found,
        "pii_log": pii_log,
        "is_safe": is_safe,
        "threat_type": threat,
        "security_notes": security_notes,
        "duplicate_detected": duplicate,
    }
    blocked = not is_safe
    return await _track(
        {
            **state,
            "redacted_issue": redacted,
            "rbac_verified": rbac_ok,
            "pii_found": pii_found,
            "pii_log": pii_log,
            "is_safe": is_safe,
            "threat_type": threat,
            "security_notes": security_notes,
            "duplicate_detected": duplicate,
            "pipeline_blocked": blocked,
            "block_reason": security_notes if blocked else "",
            "db_status": "Blocked" if blocked else state.get("db_status", "Open"),
        },
        "security_agent",
        output,
        ms,
    )


async def complaint_agent(state: MaintenanceGraphState) -> MaintenanceGraphState:
    """Node A: Parse text/images into structured issue JSON."""
    start = time.perf_counter()
    issue = state.get("redacted_issue") or state.get("original_issue", "")
    image_desc = state.get("image_desc") or "No image provided."

    system = """You are EstateFlow Complaint Agent. Input may be English, Urdu, or Roman Urdu.
Return ONLY JSON:
trade (plumbing|hvac|electrical|structural|general|appliances|pest control),
location_detail (room/area in unit),
category (Plumbing|HVAC|Electrical|Structural|General|Appliances|Pest Control),
summary (one English sentence),
vendor_specialty (same as trade),
estimated_time (e.g. 2-4 hours),
confidence (0-1)."""

    parsed = await structured_completion(
        system,
        f"Issue: {issue}\nVision: {image_desc}",
        fallback_issue=issue,
        fallback_image_desc=image_desc,
    )
    parsed, token_add = _pop_llm_tokens(parsed, state)
    trade = (parsed.get("trade") or parsed.get("vendor_specialty") or "general").lower()
    ms = int((time.perf_counter() - start) * 1000)
    output = {**parsed, "trade": trade}
    return await _track(
        {
            **state,
            "trade": trade,
            "location_detail": parsed.get("location_detail", "unknown"),
            "category": parsed.get("category", "General"),
            "summary": parsed.get("summary", issue[:200]),
            "vendor_specialty": parsed.get("vendor_specialty", trade),
            "estimated_time": parsed.get("estimated_time", "TBD"),
            "extraction_confidence": float(parsed.get("confidence", 0.8)),
            "llm_tokens_estimated": token_add,
        },
        "complaint_agent",
        output,
        ms,
    )


# ─── Phase 2: Assessment & Rules ────────────────────────────────────────────


async def priority_agent(state: MaintenanceGraphState) -> MaintenanceGraphState:
    """Node B: Risk matrix RAG + LLM urgency scoring."""
    start = time.perf_counter()
    admin = get_supabase_admin()
    issue = state.get("redacted_issue") or state.get("original_issue", "")
    property_id = state.get("property_id")

    hist_cats: list[str] = []
    if property_id:
        hist = (
            admin.table("maintenance_requests")
            .select("id")
            .eq("property_id", property_id)
            .gte("created_at", (datetime.utcnow() - timedelta(days=90)).isoformat())
            .execute()
        )
        if len(hist.data or []) >= 3:
            hist_cats = ["recurring"]

    hits, boost = lookup_risk_hits(issue, hist_cats)
    settings = get_settings()
    token_add = state.get("llm_tokens_estimated", 0)

    if settings.priority_use_llm:
        system = """Score maintenance urgency. Return ONLY JSON:
urgency (Low|Medium|High|Critical),
priority_reason (short English)."""
        parsed = await structured_completion(
            system,
            f"Issue: {issue}\nRisk hits: {hits}",
            fallback_issue=issue,
            fallback_risk_hits=hits,
            fallback_urgency_boost=boost,
        )
        parsed, token_add = _pop_llm_tokens(parsed, state)
        urgency = parsed.get("urgency", "Medium")
        priority_reason = parsed.get("priority_reason", "Risk assessment")
        if parsed.get("source") == "rule_based_fallback":
            priority_reason = (
                f"Risk matrix ({', '.join(hits) or 'none'}) — rule-based urgency (LLM skipped or rate-limited)"
            )
    else:
        parsed = parse_urgency_fast(issue, hits, boost)
        urgency = parsed.get("urgency", "Medium")
        if boost:
            order = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
            if order.get(boost, 0) > order.get(urgency, 0):
                urgency = boost
        priority_reason = (
            f"Risk matrix: {', '.join(hits) if hits else 'no rule hits'}; "
            f"urgency scored from rules (no LLM — faster & free-tier safe)."
        )

    if boost:
        order = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
        if order.get(boost, 0) > order.get(urgency, 0):
            urgency = boost

    manager_notified = False
    if urgency in ("Critical", "High"):
        ticket = state.get("request_id", "")[:8]
        count = await notify_managers_for_urgent(
            state.get("property_id"),
            f"TKT-{ticket}",
            state["request_id"],
            state.get("summary", issue[:120]),
        )
        manager_notified = count > 0
        # Also WhatsApp all managers
        try:
            wa_msg = f"URGENT [{f'TKT-{ticket}'}]: {state.get('summary', issue[:120])}. Open EstateFlow to approve."
            await send_whatsapp_to_managers(wa_msg)
        except Exception:
            pass

    ms = int((time.perf_counter() - start) * 1000)
    output = {
        "urgency": urgency,
        "priority_reason": priority_reason,
        "risk_matrix_hits": hits,
        "manager_notified": manager_notified,
        "scoring_method": "llm" if settings.priority_use_llm else "risk_matrix_rules",
    }
    return await _track(
        {**state, **output, "llm_tokens_estimated": token_add, "urgency": urgency},
        "priority_agent",
        output,
        ms,
    )


async def compliance_agent(state: MaintenanceGraphState) -> MaintenanceGraphState:
    """Node C: SLA injection and regulatory flags."""
    start = time.perf_counter()
    urgency = state.get("urgency", "Medium")
    trade = state.get("trade", "general")
    sla = SLA_BY_URGENCY.get(urgency, 48)

    flags: list[str] = []
    notes = f"Standard SLA: {sla}h resolution target."

    if urgency == "Critical":
        flags.append("emergency_response")
        notes = "Mandatory emergency SLA: 2h response for life-safety issues."
        sla = 2
    if trade == "electrical" and "water" in (state.get("summary") or "").lower():
        flags.append("electrical_water_hazard")
        notes += " Water near electrical — expedited licensed electrician required."
    if state.get("duplicate_detected"):
        flags.append("duplicate_intake_review")

    ms = int((time.perf_counter() - start) * 1000)
    output = {
        "sla_target_hours": sla,
        "compliance_notes": notes,
        "compliance_flags": flags,
        "is_compliant": True,
    }
    return await _track(
        {**state, **output},
        "compliance_agent",
        output,
        ms,
    )


# ─── Phase 3: Sourcing & Governance ─────────────────────────────────────────


async def vendor_matching_agent(state: MaintenanceGraphState) -> MaintenanceGraphState:
    """Node D: Haversine vendor match + optional external search."""
    start = time.perf_counter()
    settings = get_settings()
    admin = get_supabase_admin()

    if state.get("pipeline_blocked"):
        return await _track(state, "vendor_matching_agent", {"skipped": True}, 0)

    vendors_resp = admin.table("vendors").select("*").eq("available", True).execute()
    specialty = (state.get("vendor_specialty") or "general").lower()
    selected = rank_vendors(
        vendors_resp.data or [],
        specialty,
        state.get("latitude"),
        state.get("longitude"),
        settings.vendor_search_radius_km,
    )

    external_used = False
    license_valid = True
    if not selected and settings.enable_external_vendor_search:
        city = "Karachi"
        if state.get("property_id"):
            prop = (
                admin.table("properties")
                .select("city")
                .eq("id", state["property_id"])
                .limit(1)
                .execute()
            )
            if prop.data:
                city = prop.data[0].get("city") or city
        ext = await search_external_vendor(specialty, city)
        if ext:
            external_used = True
            selected = {
                "id": None,
                "name": ext["name"],
                "phone": ext.get("phone"),
                "distance_km": None,
                "external": True,
            }
            license_valid = False

    assigned_name = selected["name"] if selected else None
    assigned_phone = selected.get("phone") if selected else None
    assigned_id = selected.get("id") if selected else None
    distance = selected.get("distance_km") if selected else None

    ms = int((time.perf_counter() - start) * 1000)
    output = {
        "assigned_vendor": assigned_name,
        "vendor_phone": assigned_phone,
        "assigned_vendor_id": assigned_id,
        "vendor_distance_km": distance,
        "vendor_license_valid": license_valid if assigned_id else False,
        "external_search_used": external_used,
    }
    return await _track({**state, **output}, "vendor_matching_agent", output, ms)


async def governance_ethics_agent(state: MaintenanceGraphState) -> MaintenanceGraphState:
    """Node E: Fair vendor distribution, chronic complaints, human-in-the-loop gate."""
    start = time.perf_counter()
    admin = get_supabase_admin()
    flags = list(state.get("compliance_flags") or [])
    notes_parts = ["Governance audit passed."]
    approved = True
    requires_human = False

    vendor_id = state.get("assigned_vendor_id")
    if vendor_id:
        vendor = (
            admin.table("vendors")
            .select("total_assignments, name")
            .eq("id", vendor_id)
            .limit(1)
            .execute()
        )
        if vendor.data and (vendor.data[0].get("total_assignments") or 0) > 50:
            flags.append("vendor_high_load")
            notes_parts.append("Vendor has high assignment count — monitor for monopoly.")

    tenant_id = state.get("tenant_id")
    if tenant_id:
        recent = (
            admin.table("maintenance_requests")
            .select("id")
            .eq("tenant_id", tenant_id)
            .gte("created_at", (datetime.utcnow() - timedelta(days=30)).isoformat())
            .execute()
        )
        if len(recent.data or []) >= 5:
            flags.append("chronic_tenant_complaints")
            requires_human = True
            notes_parts.append("Tenant has 5+ requests in 30 days — manager review.")

    if state.get("urgency") == "Critical" and not state.get("human_approved"):
        requires_human = True
        flags.append("requires_human_approval")

    if not state.get("vendor_license_valid") and state.get("assigned_vendor"):
        flags.append("external_unverified_vendor")
        requires_human = True

    if state.get("duplicate_detected"):
        requires_human = True

    if not state.get("is_safe", True):
        approved = False

    ms = int((time.perf_counter() - start) * 1000)
    output = {
        "governance_approved": approved,
        "governance_notes": " ".join(notes_parts),
        "compliance_flags": flags,
        "requires_human_approval": requires_human,
    }
    return await _track(
        {**state, **output, "compliance_flags": flags},
        "governance_ethics_agent",
        output,
        ms,
    )


# ─── Phase 4: Execution & Communication ─────────────────────────────────────


async def scheduling_agent(state: MaintenanceGraphState) -> MaintenanceGraphState:
    """Node F: Book internal calendar slot."""
    start = time.perf_counter()

    if state.get("requires_human_approval") and not state.get("human_approved"):
        output = {"scheduling_status": "Pending Approval", "scheduled_time": None}
        return await _track(
            {
                **state,
                "scheduling_status": "Pending Approval",
                "scheduled_time": None,
                "db_status": "Pending Approval",
            },
            "scheduling_agent",
            output,
            int((time.perf_counter() - start) * 1000),
        )

    urgency = state.get("urgency", "Medium")
    hours = 2 if urgency == "Critical" else 4 if urgency == "High" else 24
    slot = datetime.utcnow() + timedelta(hours=hours)
    scheduled = slot.strftime("%Y-%m-%d %H:%M UTC")

    if state.get("assigned_vendor_id"):
        admin = get_supabase_admin()
        v = (
            admin.table("vendors")
            .select("total_assignments")
            .eq("id", state["assigned_vendor_id"])
            .limit(1)
            .execute()
        )
        if v.data:
            n = (v.data[0].get("total_assignments") or 0) + 1
            admin.table("vendors").update({"total_assignments": n}).eq(
                "id", state["assigned_vendor_id"]
            ).execute()

    ms = int((time.perf_counter() - start) * 1000)
    output = {"scheduling_status": "Confirmed", "scheduled_time": scheduled}
    return await _track(
        {
            **state,
            "scheduling_status": "Confirmed",
            "scheduled_time": scheduled,
            "db_status": "Scheduled",
        },
        "scheduling_agent",
        output,
        ms,
    )


async def communications_agent(state: MaintenanceGraphState) -> MaintenanceGraphState:
    """Node G: Tenant/manager messages (in_app; SMS/email ready via notifications table)."""
    start = time.perf_counter()
    tenant_id = state.get("tenant_id")
    urgency = state.get("urgency", "Medium")
    vendor = state.get("assigned_vendor") or "our maintenance team"
    scheduled = state.get("scheduled_time") or "soon"
    summary = state.get("summary", "your issue")

    if state.get("requires_human_approval") and not state.get("human_approved"):
        msg = (
            f"Your request ({summary}) is classified as {urgency}. "
            "A property manager must approve dispatch. You will be updated shortly."
        )
    elif state.get("scheduling_status") == "Confirmed":
        msg = (
            f"Hi — we've classified your issue as {urgency}: {summary}. "
            f"{vendor} is scheduled for {scheduled}. Thank you for reporting via EstateFlow."
        )
    else:
        msg = f"We received your request: {summary}. Status: {state.get('db_status', 'Open')}."

    sent = False
    if tenant_id:
        await notify_in_app(
            recipient_id=tenant_id,
            message=msg,
            subject="Maintenance update",
            reference_type="maintenance_request",
            reference_id=state["request_id"],
        )
        sent = True

        # WhatsApp to tenant if they have a number stored
        try:
            admin = get_supabase_admin()
            profile = (
                admin.table("profiles")
                .select("whatsapp_phone")
                .eq("id", tenant_id)
                .limit(1)
                .execute()
            )
            tenant_wa = (profile.data or [{}])[0].get("whatsapp_phone") or ""
            if tenant_wa:
                await send_whatsapp(tenant_wa, msg)
        except Exception:
            pass  # WhatsApp failure must never block the pipeline

    # WhatsApp to vendor when job is confirmed
    vendor_phone = state.get("vendor_phone") or ""
    if vendor_phone and state.get("scheduling_status") == "Confirmed":
        vendor_msg = (
            f"New EstateFlow job assigned.\n"
            f"Issue: {summary}\n"
            f"Scheduled: {scheduled}\n"
            f"Ticket: {state.get('request_id', '')[:8].upper()}"
        )
        try:
            await send_whatsapp(vendor_phone, vendor_msg)
        except Exception:
            pass

    follow_up = schedule_follow_up_iso(24)
    ms = int((time.perf_counter() - start) * 1000)
    output = {"tenant_message": msg, "notification_sent": sent, "follow_up_at": follow_up}
    return await _track(
        {**state, **output, "follow_up_at": follow_up},
        "communications_agent",
        output,
        ms,
    )


async def report_agent(state: MaintenanceGraphState) -> MaintenanceGraphState:
    """Node I: Formal paperwork — PDF, AI summary, audit ledger; pauses for manager sign-off."""
    start = time.perf_counter()
    admin = get_supabase_admin()
    request_id = state["request_id"]

    req = (
        admin.table("maintenance_requests")
        .select("ticket_id")
        .eq("id", request_id)
        .limit(1)
        .execute()
    )
    ticket_id = (req.data or [{}])[0].get("ticket_id") or f"TKT-{request_id[:8].upper()}"

    needs_signature = bool(
        state.get("requires_human_approval")
        or state.get("urgency") in ("Critical", "High")
    )
    signed = bool(state.get("human_approved") or state.get("report_signed"))
    draft = needs_signature and not signed

    report_summary = build_report_summary(state, ticket_id)
    audit_ledger = build_audit_ledger(state, ticket_id)
    pdf_bytes = render_maintenance_pdf(
        state, ticket_id, report_summary, audit_ledger, draft=draft
    )
    pdf_path = await upload_report_pdf(request_id, pdf_bytes, draft=draft)

    report_pending_signature = draft
    report_signed = signed and not draft

    if draft:
        db_status = "Pending Approval"
        for mid in await _manager_ids(admin):
            await notify_in_app(
                recipient_id=mid,
                message=(
                    f"Report ready for signature — {ticket_id}. "
                    f"Review PDF and approve dispatch in EstateFlow Approvals."
                ),
                subject="Maintenance report — signature required",
                reference_type="maintenance_request",
                reference_id=request_id,
            )
    else:
        db_status = state.get("db_status") or "In Progress"

    ms = int((time.perf_counter() - start) * 1000)
    output = {
        "report_summary": report_summary[:2000],
        "report_pdf_path": pdf_path,
        "audit_ledger": audit_ledger,
        "report_pending_signature": report_pending_signature,
        "report_signed": report_signed,
        "draft": draft,
    }
    return await _track(
        {
            **state,
            "report_summary": report_summary[:2000],
            "report_pdf_path": pdf_path,
            "audit_ledger": audit_ledger,
            "report_pending_signature": report_pending_signature,
            "report_signed": report_signed,
            "db_status": db_status,
        },
        "report_agent",
        output,
        ms,
    )


async def _manager_ids(admin) -> list[str]:
    rows = (
        admin.table("profiles")
        .select("id")
        .in_("role", ["manager", "admin"])
        .execute()
    )
    return [str(r["id"]) for r in (rows.data or [])]


async def performance_agent(state: MaintenanceGraphState) -> MaintenanceGraphState:
    """Meta-node #11: latency, tokens, hallucination risk, alerts, model routing hints."""
    start = time.perf_counter()
    settings = get_settings()
    timings = state.get("node_timings_ms") or {}
    total_ms = sum(timings.values())
    agent_count = len(state.get("agents_run") or [])
    tokens = state.get("llm_tokens_estimated", 0)

    urgency = state.get("urgency", "Medium")
    score = {"Low": 92, "Medium": 78, "High": 62, "Critical": 45}.get(urgency, 70)
    if state.get("assigned_vendor"):
        score += 5
    if state.get("pipeline_blocked"):
        score = 10
    if state.get("report_pending_signature"):
        score -= 10

    alerts: list[str] = []
    if total_ms > 60_000:
        alerts.append("workflow_slow: pipeline exceeded 60s")
    if tokens > 8000:
        alerts.append("token_usage_high: consider shorter prompts or rule-based fallback")
    if state.get("pipeline_blocked"):
        alerts.append("workflow_blocked: security or governance halt")
    if not state.get("is_safe", True):
        alerts.append("security_failure: request blocked")
    if state.get("requires_human_approval") and not state.get("human_approved"):
        alerts.append("awaiting_human_approval")

    confidence = float(state.get("extraction_confidence", 0.85))
    hallucination_risk = "low"
    if confidence < 0.6:
        hallucination_risk = "high"
        alerts.append("hallucination_risk_high: low complaint extraction confidence")
    elif confidence < 0.75:
        hallucination_risk = "medium"

    if state.get("scheduling_status") == "Confirmed" and not state.get("assigned_vendor"):
        hallucination_risk = "medium"
        alerts.append("data_inconsistency: scheduled without vendor")

    recommended_model = settings.openrouter_model
    if total_ms > 45_000 or tokens > 5000:
        recommended_model = "nvidia/nemotron-nano-9b-v2:free"

    notes = (
        f"Pipeline {total_ms}ms | {agent_count} agents | ~{tokens} tokens | "
        f"hallucination_risk={hallucination_risk} | model={settings.openrouter_model} | "
        f"alerts={alerts or 'none'}"
    )

    ms = int((time.perf_counter() - start) * 1000)
    output = {
        "performance_score": score,
        "performance_notes": notes,
        "performance_alerts": alerts,
        "recommended_model": recommended_model,
        "hallucination_risk": hallucination_risk,
        "total_pipeline_ms": total_ms + ms,
        "token_usage_estimate": tokens,
    }
    return await _track(
        {
            **state,
            "performance_score": score,
            "performance_notes": notes,
            "performance_alerts": alerts,
            "recommended_model": recommended_model,
            "hallucination_risk": hallucination_risk,
            "total_pipeline_ms": total_ms + ms,
            "llm_tokens_estimated": tokens,
        },
        "performance_agent",
        output,
        ms,
    )


# ─── Routers ─────────────────────────────────────────────────────────────────


def route_after_security(state: MaintenanceGraphState) -> str:
    if state.get("pipeline_blocked") or not state.get("is_safe", True):
        return "blocked"
    return "continue"


def route_after_governance(state: MaintenanceGraphState) -> str:
    if not state.get("governance_approved", True):
        return "blocked"
    if state.get("requires_human_approval") and not state.get("human_approved"):
        return "await_human"
    return "continue"


def route_after_report(state: MaintenanceGraphState) -> str:
    """Pause after Report Agent until manager signs (human approval breakpoint)."""
    if state.get("report_pending_signature") and not state.get("report_signed"):
        return "await_signature"
    return "continue"
