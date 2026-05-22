"""
Invoke EstateFlow Calendar MCP tools from the FastAPI backend / LangGraph agents.

Uses stdio MCP when MCP_CALENDAR_USE_STDIO=true; otherwise calls calendar_service in-process
(same logic the MCP server exposes).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.config import get_settings
from app.services.calendar_service import (
    book_maintenance_on_both_calendars,
    calendar_connected_for_user,
    create_event_for_profile,
    create_event_for_vendor,
    profile_has_calendar,
    vendor_has_calendar,
)

logger = logging.getLogger(__name__)


async def _call_mcp_stdio(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    settings = get_settings()
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env = {
        **os.environ,
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_SERVICE_ROLE_KEY": settings.supabase_service_role_key,
        "GOOGLE_OAUTH_CLIENT_ID": settings.google_oauth_client_id,
        "GOOGLE_OAUTH_CLIENT_SECRET": settings.google_oauth_client_secret,
        "CALENDAR_TOKEN_ENCRYPTION_KEY": settings.calendar_token_encryption_key,
    }
    params = StdioServerParameters(
        command="python",
        args=["-m", "mcp_servers.estateflow_calendar"],
        cwd=backend_dir,
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            if result.content:
                text = getattr(result.content[0], "text", None) or str(result.content[0])
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw": text}
            return {"ok": True}


def _inprocess_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "calendar_connection_status":
        pid = arguments["profile_id"]
        return {"profile_id": pid, "connected": profile_has_calendar(pid)}
    if tool_name == "calendar_create_event":
        return create_event_for_profile(
            arguments["profile_id"],
            summary=arguments["summary"],
            start_iso=arguments["start_iso"],
            end_iso=arguments.get("end_iso") or None,
            description=arguments.get("description", ""),
        )
    if tool_name == "calendar_book_maintenance_pair":
        return book_maintenance_on_both_calendars(
            tenant_profile_id=arguments.get("tenant_profile_id") or None,
            vendor_id=arguments.get("vendor_profile_id") or arguments.get("vendor_id") or None,
            summary=arguments["summary"],
            scheduled_iso=arguments.get("start_iso"),
            request_id=arguments["request_id"],
        )
    if tool_name == "calendar_vendor_profile_id":
        vid = arguments["vendor_id"]
        return {"vendor_id": vid, "calendar_connected": vendor_has_calendar(vid)}
    raise ValueError(f"Unknown MCP tool: {tool_name}")


async def mcp_calendar_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if settings.mcp_calendar_use_stdio:
        try:
            return await _call_mcp_stdio(tool_name, arguments)
        except Exception as exc:
            logger.warning("MCP stdio failed (%s), using in-process calendar", exc)
    return _inprocess_tool(tool_name, arguments)


async def mcp_book_maintenance_pair(
    *,
    tenant_profile_id: str | None,
    vendor_profile_id: str | None,
    summary: str,
    start_iso: str | None,
    request_id: str,
) -> dict[str, Any]:
    return await mcp_calendar_tool(
        "calendar_book_maintenance_pair",
        {
            "tenant_profile_id": tenant_profile_id or "",
            "vendor_profile_id": vendor_profile_id or "",
            "vendor_id": vendor_profile_id or "",
            "summary": summary,
            "start_iso": start_iso or "",
            "request_id": request_id,
        },
    )
