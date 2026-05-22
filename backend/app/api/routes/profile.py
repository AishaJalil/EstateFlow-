from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.db import get_supabase_admin
from app.schemas import ProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {"data": user}


@router.patch("/me")
@router.put("/me")
async def update_me(body: ProfileUpdate, user: dict = Depends(get_current_user)):
    admin = get_supabase_admin()
    payload = body.model_dump(exclude_none=True)
    if not payload:
        return {"data": user}
    result = admin.table("profiles").update(payload).eq("id", user["id"]).execute()
    updated = result.data[0] if result.data else user
    # Re-attach email from the user dict (profiles table doesn't store email)
    updated["email"] = user.get("email", "")
    return {"data": updated}
