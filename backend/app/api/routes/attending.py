from fastapi import APIRouter, Depends

from app.core.deps import require_role
from app.models.user import RoleEnum, User

router = APIRouter(tags=["attending"])


@router.get("/attending/dashboard")
def attending_dashboard(
    current_user: User = Depends(require_role(RoleEnum.attending)),
) -> dict[str, str]:
    return {"message": f"Welcome, {current_user.full_name}"}
