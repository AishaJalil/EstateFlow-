import time
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.nodes import (
    communications_agent,
    complaint_agent,
    compliance_agent,
    governance_ethics_agent,
    performance_agent,
    priority_agent,
    report_agent,
    route_after_governance,
    route_after_report,
    route_after_security,
    scheduling_agent,
    security_agent,
    vendor_matching_agent,
    vendor_outreach_agent,
)
from app.agents.state import MaintenanceGraphState
from app.agents.progress import init_pipeline_progress
from app.db import get_supabase_admin


def build_maintenance_graph():
    """
    Production maintenance pipeline (real-time loop ends after communications_agent).

    security → complaint → priority → compliance → vendor_matching
      → governance_ethics → [human gate] → scheduling → communications
      → report_agent → [manager sign] → performance_agent → END
    """
    graph = StateGraph(MaintenanceGraphState)

    graph.add_node("security_agent", security_agent)
    graph.add_node("complaint_agent", complaint_agent)
    graph.add_node("priority_agent", priority_agent)
    graph.add_node("compliance_agent", compliance_agent)
    graph.add_node("vendor_matching_agent", vendor_matching_agent)
    graph.add_node("governance_ethics_agent", governance_ethics_agent)
    graph.add_node("vendor_outreach_agent", vendor_outreach_agent)
    graph.add_node("scheduling_agent", scheduling_agent)
    graph.add_node("communications_agent", communications_agent)
    graph.add_node("report_agent", report_agent)
    graph.add_node("performance_agent", performance_agent)

    graph.set_entry_point("security_agent")

    graph.add_conditional_edges(
        "security_agent",
        route_after_security,
        {"blocked": END, "continue": "complaint_agent"},
    )
    graph.add_edge("complaint_agent", "priority_agent")
    graph.add_edge("priority_agent", "compliance_agent")
    graph.add_edge("compliance_agent", "vendor_matching_agent")
    graph.add_edge("vendor_matching_agent", "governance_ethics_agent")

    graph.add_conditional_edges(
        "governance_ethics_agent",
        route_after_governance,
        {
            "blocked": END,
            "await_human": "vendor_outreach_agent",
            "continue": "vendor_outreach_agent",
        },
    )
    graph.add_edge("vendor_outreach_agent", "scheduling_agent")
    graph.add_edge("scheduling_agent", "communications_agent")
    graph.add_edge("communications_agent", "report_agent")
    graph.add_conditional_edges(
        "report_agent",
        route_after_report,
        {"await_signature": END, "continue": "performance_agent"},
    )
    graph.add_edge("performance_agent", END)

    return graph.compile()


async def schedule_verification_followup(state: MaintenanceGraphState) -> None:
    """Node H (async): queue 24h tenant follow-up via notifications."""
    admin = get_supabase_admin()
    tenant_id = state.get("tenant_id")
    if not tenant_id:
        return

    follow_up = state.get("follow_up_at")
    msg = (
        "Follow-up: Did the maintenance visit resolve your issue? "
        "Reply in EstateFlow or contact your property manager."
    )
    admin.table("notifications").insert(
        {
            "type": "in_app",
            "recipient_id": tenant_id,
            "subject": "Maintenance follow-up",
            "message": msg,
            "reference_type": "maintenance_request",
            "reference_id": state["request_id"],
            "status": "pending",
        }
    ).execute()

    try:
        admin.table("maintenance_requests").update(
            {"status": "In Progress"}
        ).eq("id", state["request_id"]).execute()
    except Exception:
        pass


async def persist_pipeline_result(state: MaintenanceGraphState, duration_ms: int) -> None:
    admin = get_supabase_admin()
    request_id = state["request_id"]

    pipeline_row = {
        "request_id": request_id,
        "category": state.get("category"),
        "urgency": state.get("urgency"),
        "summary": state.get("summary"),
        "vendor_specialty": state.get("vendor_specialty"),
        "estimated_time": state.get("estimated_time"),
        "priority_reason": state.get("priority_reason"),
        "duration_ms": duration_ms,
        "agents_run": state.get("agents_run", []),
        "pii_found": state.get("pii_found", False),
        "pii_log": state.get("pii_log"),
        "is_safe": state.get("is_safe", True),
        "security_notes": state.get("security_notes"),
        "threat_type": state.get("threat_type", "none"),
        "is_compliant": state.get("is_compliant", True),
        "governance_notes": state.get("governance_notes"),
        "compliance_flags": state.get("compliance_flags", []),
        "performance_score": state.get("performance_score"),
        "sla_target_hours": state.get("sla_target_hours"),
        "performance_notes": state.get("performance_notes"),
        "assigned_vendor": state.get("assigned_vendor"),
        "vendor_phone": state.get("vendor_phone"),
        "assigned_vendor_id": state.get("assigned_vendor_id"),
        "scheduled_time": state.get("scheduled_time"),
        "db_status": state.get("db_status"),
        "human_approved": state.get("human_approved", False),
        "report_summary": state.get("report_summary"),
        "report_pdf_path": state.get("report_pdf_path"),
        "report_signed": state.get("report_signed", False),
        "report_pending_signature": state.get("report_pending_signature", False),
        "audit_ledger": state.get("audit_ledger", []),
        "token_usage_estimate": state.get("llm_tokens_estimated"),
        "performance_alerts": state.get("performance_alerts", []),
        "recommended_model": state.get("recommended_model"),
    }

    existing = (
        admin.table("maintenance_pipeline_results")
        .select("id")
        .eq("request_id", request_id)
        .execute()
    )
    if existing.data:
        admin.table("maintenance_pipeline_results").update(pipeline_row).eq(
            "request_id", request_id
        ).execute()
    else:
        admin.table("maintenance_pipeline_results").insert(pipeline_row).execute()

    status = state.get("db_status") or "Open"
    if state.get("report_pending_signature") and not state.get("report_signed"):
        status = "Pending Approval"
    elif state.get("requires_human_approval") and not state.get("human_approved"):
        status = "Pending Approval"
    if state.get("pipeline_blocked"):
        status = "Blocked"

    update_row: dict[str, Any] = {
        "redacted_issue": state.get("redacted_issue"),
        "image_desc": state.get("image_desc"),
        "status": status,
    }
    admin.table("maintenance_requests").update(update_row).eq("id", request_id).execute()

    # Agent steps are logged incrementally in persist_agent_step during graph run.


async def run_maintenance_pipeline(initial: MaintenanceGraphState) -> dict[str, Any]:
    await init_pipeline_progress(initial["request_id"])
    graph = build_maintenance_graph()
    start = time.perf_counter()
    final_state = await graph.ainvoke(initial)
    duration_ms = int((time.perf_counter() - start) * 1000)
    await persist_pipeline_result(final_state, duration_ms)
    await schedule_verification_followup(final_state)
    return {**final_state, "duration_ms": duration_ms}
