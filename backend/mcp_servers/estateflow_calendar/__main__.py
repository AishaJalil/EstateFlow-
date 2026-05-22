"""
MCP server (stdio) for EstateFlow calendar tools.

Configure in Cursor (.cursor/mcp.json):
  "estateflow-calendar": {
    "command": "python",
    "args": ["-m", "mcp_servers.estateflow_calendar"],
    "cwd": "<repo>/backend",
    "env": { "SUPABASE_URL": "...", "SUPABASE_SERVICE_ROLE_KEY": "...", ... }
  }

Tools load OAuth tokens per profile_id from calendar_connections — scales to many users
because each call only touches the profiles involved in that booking.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure backend package is importable when run as -m mcp_servers.estateflow_calendar
_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastmcp import FastMCP

from app.services.calendar_service import (
    book_maintenance_on_both_calendars,
    create_event_for_profile,
    profile_has_calendar,
    vendor_profile_id_for_vendor,
)

mcp = FastMCP(
    "EstateFlow Calendar",
    instructions=(
        "Google Calendar tools for EstateFlow. Each tool takes a profile_id (tenant or vendor user) "
        "and uses that person's stored OAuth connection. For maintenance bookings use "
        "book_maintenance_pair with tenant and vendor profile IDs."
    ),
)


@mcp.tool
def calendar_connection_status(profile_id: str) -> dict:
    """Check whether a user has connected Google Calendar."""
    return {"profile_id": profile_id, "connected": profile_has_calendar(profile_id)}


@mcp.tool
def calendar_create_event(
    profile_id: str,
    summary: str,
    start_iso: str,
    end_iso: str = "",
    description: str = "",
) -> dict:
    """Create an event on one user's Google Calendar (uses their OAuth tokens)."""
    return create_event_for_profile(
        profile_id,
        summary=summary,
        start_iso=start_iso,
        end_iso=end_iso or None,
        description=description,
    )


@mcp.tool
def calendar_book_maintenance_pair(
    tenant_profile_id: str,
    vendor_profile_id: str,
    summary: str,
    start_iso: str,
    request_id: str,
) -> dict:
    """
    Book the same maintenance visit on tenant and vendor calendars.
    Pass empty string for a profile_id if that party has not connected calendar yet.
    """
    return book_maintenance_on_both_calendars(
        tenant_profile_id=tenant_profile_id or None,
        vendor_id=vendor_profile_id or None,
        summary=summary,
        scheduled_iso=start_iso or None,
        request_id=request_id,
    )


@mcp.tool
def calendar_vendor_profile_id(vendor_id: str) -> dict:
    """Resolve vendor directory UUID to the vendor user's profile_id for calendar tools."""
    pid = vendor_profile_id_for_vendor(vendor_id)
    return {"vendor_id": vendor_id, "vendor_profile_id": pid}


if __name__ == "__main__":
    mcp.run()
