import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from app.agents.maintenance_graph import run_maintenance_pipeline
from app.auth import get_current_user, require_roles
from app.db import get_supabase_admin
from app.schemas import MaintenanceApprove, MaintenanceCreate, MaintenanceFeedback
from app.services.llm import structured_completion

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


def _normalize_pipeline(row: dict) -> dict | None:
    pl = row.get("maintenance_pipeline_results")
    if not pl:
        return None
    if isinstance(pl, list):
        return pl[0] if pl else None
    return pl


def _needs_manager_approval(row: dict) -> bool:
    if row.get("status") == "Pending Approval":
        return True
    pl = _normalize_pipeline(row)
    if not pl:
        return False
    if pl.get("report_pending_signature") and not pl.get("report_signed"):
        return True
    agents = pl.get("agents_run") or []
    if "report_agent" in agents and "performance_agent" not in agents:
        return True
    if pl.get("urgency") in ("Critical", "High") and not pl.get("human_approved"):
        return True
    return False


def _generate_ticket_id() -> str:
    return f"TKT-{uuid.uuid4().hex[:8].upper()}"


async def _describe_images(files: list[UploadFile]) -> str:
    if not files:
        return "No image provided."
    names = [f.filename or "image" for f in files[:5]]
    return f"Tenant uploaded {len(files)} file(s): {', '.join(names)}. Vision analysis pending."


async def _upload_media(request_id: str, files: list[UploadFile]) -> list[str]:
    admin = get_supabase_admin()
    paths: list[str] = []
    bucket = "maintenance-media"

    for f in files:
        content = await f.read()
        if not content:
            continue
        ext = (f.filename or "img.jpg").split(".")[-1]
        path = f"{request_id}/{uuid.uuid4().hex}.{ext}"
        try:
            admin.storage.from_(bucket).upload(
                path,
                content,
                {"content-type": f.content_type or "application/octet-stream"},
            )
        except Exception:
            # Bucket may not exist yet — store path only
            pass
        admin.table("maintenance_request_media").insert(
            {"request_id": request_id, "storage_path": path, "mime_type": f.content_type}
        ).execute()
        paths.append(path)
    return paths


@router.get("")
async def list_requests(user: dict = Depends(get_current_user)):
    admin = get_supabase_admin()
    query = admin.table("maintenance_requests").select(
        "*, maintenance_pipeline_results(*)"
    ).order("created_at", desc=True)

    if user["role"] == "tenant":
        query = query.eq("tenant_id", user["id"])

    result = query.execute()
    return {"data": result.data or []}


@router.get("/pending-approvals")
async def list_pending_approvals(
    user: dict = Depends(require_roles("admin", "manager")),
):
    """Requests waiting for manager approval or report signature."""
    admin = get_supabase_admin()
    result = (
        admin.table("maintenance_requests")
        .select("*, maintenance_pipeline_results(*)")
        .order("created_at", desc=True)
        .execute()
    )
    pending = [r for r in (result.data or []) if _needs_manager_approval(r)]
    return {"data": pending, "count": len(pending)}


@router.get("/{request_id}")
async def get_request(request_id: str, user: dict = Depends(get_current_user)):
    admin = get_supabase_admin()
    result = (
        admin.table("maintenance_requests")
        .select("*, maintenance_pipeline_results(*), maintenance_request_media(*)")
        .eq("id", request_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Request not found")
    if user["role"] == "tenant" and result.data.get("tenant_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"data": result.data}


@router.post("")
async def create_request(
    background_tasks: BackgroundTasks,
    body: MaintenanceCreate,
    user: dict = Depends(get_current_user),
):
    admin = get_supabase_admin()
    ticket_id = _generate_ticket_id()
    row = {
        "ticket_id": ticket_id,
        "tenant_name": user.get("full_name") or "Tenant",
        "tenant_id": user["id"],
        "unit": body.unit,
        "property_id": body.property_id,
        "property_name": body.property_name,
        "original_issue": body.original_issue,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "status": "Open",
    }
    inserted = admin.table("maintenance_requests").insert(row).execute()
    request = inserted.data[0]
    request_id = request["id"]

    initial_state = {
        "request_id": request_id,
        "tenant_id": user["id"],
        "property_id": body.property_id,
        "original_issue": body.original_issue,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "image_desc": "No image provided.",
        "agents_run": [],
        "agent_outputs": {},
        "human_approved": False,
    }
    background_tasks.add_task(run_maintenance_pipeline, initial_state)

    return {
        "data": request,
        "request_id": request_id,
        "message": "Request submitted. AI pipeline processing.",
    }


@router.post("/submit-with-media")
async def submit_with_media(
    background_tasks: BackgroundTasks,
    property_id: Annotated[str | None, Form()] = None,
    unit: Annotated[str, Form()] = ...,
    property_name: Annotated[str, Form()] = ...,
    original_issue: Annotated[str, Form()] = ...,
    latitude: Annotated[float | None, Form()] = None,
    longitude: Annotated[float | None, Form()] = None,
    images: Annotated[list[UploadFile], File()] = [],
    user: dict = Depends(get_current_user),
):
    admin = get_supabase_admin()
    ticket_id = _generate_ticket_id()
    image_desc = await _describe_images(images)

    row = {
        "ticket_id": ticket_id,
        "tenant_name": user.get("full_name") or "Tenant",
        "tenant_id": user["id"],
        "unit": unit,
        "property_id": property_id,
        "property_name": property_name,
        "original_issue": original_issue,
        "latitude": latitude,
        "longitude": longitude,
        "status": "Open",
    }
    inserted = admin.table("maintenance_requests").insert(row).execute()
    request = inserted.data[0]
    request_id = request["id"]

    if images:
        await _upload_media(request_id, images)
        try:
            vision = await structured_completion(
                "Describe property maintenance damage from tenant photo metadata. Return JSON: {image_desc: string}",
                image_desc,
            )
            image_desc = vision.get("image_desc", image_desc)
        except Exception:
            pass

    initial_state = {
        "request_id": request_id,
        "tenant_id": user["id"],
        "property_id": property_id,
        "original_issue": original_issue,
        "latitude": latitude,
        "longitude": longitude,
        "image_desc": image_desc,
        "agents_run": [],
        "agent_outputs": {},
        "node_timings_ms": {},
        "human_approved": False,
    }
    background_tasks.add_task(run_maintenance_pipeline, initial_state)

    return {
        "data": request,
        "request_id": request_id,
        "message": "Request submitted. Multi-agent pipeline started.",
    }


@router.post("/{request_id}/approve")
async def approve_request(
    request_id: str,
    body: MaintenanceApprove,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_roles("admin", "manager")),
):
    admin = get_supabase_admin()
    req = (
        admin.table("maintenance_requests")
        .select("*")
        .eq("id", request_id)
        .single()
        .execute()
    )
    if not req.data:
        raise HTTPException(status_code=404, detail="Request not found")

    pipeline = (
        admin.table("maintenance_pipeline_results")
        .select("*")
        .eq("request_id", request_id)
        .limit(1)
        .execute()
    )

    if not body.approved:
        admin.table("maintenance_requests").update({"status": "Open"}).eq("id", request_id).execute()
        return {"message": "Approval rejected"}

    initial_state = {
        "request_id": request_id,
        "tenant_id": req.data.get("tenant_id"),
        "property_id": req.data.get("property_id"),
        "original_issue": req.data["original_issue"],
        "latitude": req.data.get("latitude"),
        "longitude": req.data.get("longitude"),
        "image_desc": req.data.get("image_desc") or "No image provided.",
        "human_approved": True,
        "report_signed": True,
        "agents_run": [],
        "agent_outputs": {},
    }

    pl = (pipeline.data or [None])[0]
    if pl:
        initial_state.update(
            {
                "category": pl.get("category"),
                "urgency": pl.get("urgency"),
                "vendor_specialty": pl.get("vendor_specialty"),
                "summary": pl.get("summary"),
                "is_safe": pl.get("is_safe", True),
                "is_compliant": True,
            }
        )

    background_tasks.add_task(run_maintenance_pipeline, initial_state)
    return {"message": "Approved. Dispatch pipeline re-running."}


@router.get("/{request_id}/pipeline")
async def get_pipeline(request_id: str, user: dict = Depends(get_current_user)):
    admin = get_supabase_admin()
    result = (
        admin.table("maintenance_pipeline_results")
        .select("*")
        .eq("request_id", request_id)
        .limit(1)
        .execute()
    )
    logs = (
        admin.table("agent_logs")
        .select("*")
        .eq("reference_id", request_id)
        .eq("pipeline_type", "maintenance")
        .order("created_at")
        .execute()
    )
    return {"pipeline": (result.data or [None])[0], "agent_logs": logs.data or []}


@router.get("/{request_id}/report")
async def get_report_meta(request_id: str, user: dict = Depends(get_current_user)):
    """Report Agent output: summary, PDF path, audit ledger."""
    admin = get_supabase_admin()
    req = (
        admin.table("maintenance_requests")
        .select("tenant_id")
        .eq("id", request_id)
        .single()
        .execute()
    )
    if not req.data:
        raise HTTPException(status_code=404, detail="Request not found")
    if user["role"] == "tenant" and req.data.get("tenant_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    pl = (
        admin.table("maintenance_pipeline_results")
        .select(
            "report_summary, report_pdf_path, report_signed, "
            "report_pending_signature, audit_ledger"
        )
        .eq("request_id", request_id)
        .limit(1)
        .execute()
    )
    row = (pl.data or [None])[0]
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {"data": row}


@router.post("/{request_id}/resolve")
async def resolve_request(
    request_id: str,
    user: dict = Depends(get_current_user),
):
    """Tenant (or manager/admin) marks a request as Resolved."""
    admin = get_supabase_admin()
    req = (
        admin.table("maintenance_requests")
        .select("tenant_id, status")
        .eq("id", request_id)
        .single()
        .execute()
    )
    if not req.data:
        raise HTTPException(status_code=404, detail="Request not found")
    if user["role"] == "tenant" and req.data.get("tenant_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    admin.table("maintenance_requests").update({"status": "Resolved"}).eq(
        "id", request_id
    ).execute()
    return {"message": "Request marked as Resolved."}


@router.post("/{request_id}/feedback")
async def submit_feedback(
    request_id: str,
    body: MaintenanceFeedback,
    user: dict = Depends(get_current_user),
):
    """Tenant confirms whether the repair resolved their issue (follow-up response)."""


    admin = get_supabase_admin()
    req = (
        admin.table("maintenance_requests")
        .select("tenant_id, status")
        .eq("id", request_id)
        .single()
        .execute()
    )
    if not req.data:
        raise HTTPException(status_code=404, detail="Request not found")
    if user["role"] == "tenant" and req.data.get("tenant_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    update: dict = {"tenant_feedback": body.comment}
    if body.confirmed_resolved:
        update["tenant_confirmed_resolved"] = True
        update["status"] = "Resolved"
    else:
        # Not resolved — reopen
        update["tenant_confirmed_resolved"] = False
        update["status"] = "Open"

    admin.table("maintenance_requests").update(update).eq("id", request_id).execute()
    return {"message": "Feedback recorded. Thank you!"}

