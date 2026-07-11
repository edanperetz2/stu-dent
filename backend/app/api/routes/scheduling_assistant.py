from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.database import get_db
from app.models.user import RoleEnum, User
from app.schemas.scheduling_assistant import InterpretedAppointmentOut, InterpretRequestIn
from app.services.scheduling_interpreter import interpret_request

router = APIRouter(tags=["scheduling-assistant"])


@router.post("/scheduling/interpret", response_model=InterpretedAppointmentOut)
def interpret_scheduling_request(
    payload: InterpretRequestIn,
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.patient)),
    db: Session = Depends(get_db),
) -> InterpretedAppointmentOut:
    return interpret_request(db, user=current_user, text=payload.text)
