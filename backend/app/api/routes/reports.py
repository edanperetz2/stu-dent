from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.database import get_db
from app.models.report import Report, ReportPeriodType
from app.models.user import RoleEnum, User
from app.schemas.report import AskQuestionIn, ReportOut
from app.services.report_assistant import answer_ad_hoc_question, generate_periodic_report

router = APIRouter(tags=["reports"])


@router.get("/reports", response_model=list[ReportOut])
def list_reports(
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.attending)),
    db: Session = Depends(get_db),
) -> list[Report]:
    stmt = (
        select(Report)
        .where(Report.recipient_id == current_user.id)
        .order_by(Report.created_at.desc())
    )
    return list(db.scalars(stmt))


@router.post("/reports/generate", response_model=list[ReportOut], status_code=201)
def generate_report_now(
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.attending)),
    db: Session = Depends(get_db),
) -> list[Report]:
    """Manual trigger for demo/testing convenience -- generates a weekly
    and a monthly report immediately using a rolling window rather than
    waiting for a calendar boundary like the worker's scheduled pass does.
    """
    now = datetime.now(UTC)
    weekly = generate_periodic_report(
        db,
        current_user,
        period_type=ReportPeriodType.weekly,
        period_start=now - timedelta(days=7),
        period_end=now,
    )
    monthly = generate_periodic_report(
        db,
        current_user,
        period_type=ReportPeriodType.monthly,
        period_start=now - timedelta(days=30),
        period_end=now,
    )
    return [weekly, monthly]


@router.post("/reports/ask", response_model=ReportOut, status_code=201)
def ask_question(
    payload: AskQuestionIn,
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.attending)),
    db: Session = Depends(get_db),
) -> Report:
    return answer_ad_hoc_question(db, current_user, payload.question)
