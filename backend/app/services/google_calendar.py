"""Maintenance booking — routed through MCP calendar tools."""

import logging
from typing import Any

from app.mcp.client import mcp_book_maintenance_pair

logger = logging.getLogger(__name__)


async def book_maintenance_appointment(
    *,
    summary: str,
    scheduled_iso: str | None,
    tenant_email: str | None,
    vendor_email: str | None,
    request_id: str,
    tenant_profile_id: str | None = None,
    vendor_id: str | None = None,
) -> dict[str, Any]:
    result = await mcp_book_maintenance_pair(
        tenant_profile_id=tenant_profile_id,
        vendor_profile_id=vendor_id,
        summary=summary,
        start_iso=scheduled_iso,
        request_id=request_id,
    )

    start = result.get("start")
    tenant_ev = result.get("tenant_event_id")
    vendor_ev = result.get("vendor_event_id")

    if not tenant_ev and not vendor_ev:
        logger.info(
            "MCP calendar booking: no connected calendars for request %s",
            request_id,
        )

    return {
        "enabled": True,
        "mcp": True,
        "tenant_event_id": tenant_ev,
        "vendor_event_id": vendor_ev,
        "start": start,
        "end": result.get("end"),
        "details": result,
    }
