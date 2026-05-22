from typing import Any, TypedDict


class MaintenanceGraphState(TypedDict, total=False):
    # Context
    request_id: str
    tenant_id: str
    property_id: str | None
    tenant_role: str
    original_issue: str
    redacted_issue: str
    image_desc: str
    latitude: float | None
    longitude: float | None
    human_approved: bool

    # Phase 1 — Security & Complaint
    rbac_verified: bool
    pii_found: bool
    pii_log: str
    is_safe: bool
    security_notes: str
    threat_type: str
    duplicate_detected: bool
    trade: str
    location_detail: str
    category: str
    summary: str
    vendor_specialty: str
    estimated_time: str
    extraction_confidence: float

    # Phase 2 — Priority & Compliance
    urgency: str  # Low | Medium | High | Critical
    priority_reason: str
    risk_matrix_hits: list[str]
    manager_notified: bool
    sla_target_hours: int
    compliance_notes: str
    compliance_flags: list[str]
    is_compliant: bool

    # Phase 3 — Vendor & Governance
    ranked_vendor_ids: list[str]
    ranked_vendors: list[dict[str, Any]]
    outreach_started: bool
    outreach_thread_id: str | None
    assigned_vendor: str | None
    vendor_phone: str | None
    assigned_vendor_id: str | None
    vendor_distance_km: float | None
    vendor_license_valid: bool
    external_search_used: bool
    governance_approved: bool
    governance_notes: str
    requires_human_approval: bool

    # Phase 4 — Scheduling & Communications
    scheduled_time: str | None
    scheduling_status: str
    tenant_message: str
    notification_sent: bool
    follow_up_at: str | None

    # Phase 5 — Report (Node I)
    report_summary: str
    report_pdf_path: str
    report_signed: bool
    report_pending_signature: bool
    audit_ledger: list[dict[str, Any]]

    # Phase 6 — Meta (Performance Agent)
    performance_score: int
    performance_notes: str
    performance_alerts: list[str]
    recommended_model: str
    hallucination_risk: str
    llm_tokens_estimated: int
    total_pipeline_ms: int
    db_status: str
    pipeline_blocked: bool
    block_reason: str

    agents_run: list[str]
    agent_outputs: dict[str, Any]
    node_timings_ms: dict[str, int]
    error_log: list[str]
