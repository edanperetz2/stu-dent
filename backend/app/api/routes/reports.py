from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.database import get_db
from app.models.report import Report, ReportPeriodType
from app.models.user import RoleEnum, User
from app.schemas.report import AskQuestionIn, GenerateReportIn, ReportOut
from app.services.report_assistant import answer_ad_hoc_question, generate_periodic_report

router = APIRouter(tags=["reports"])


@router.get("/reports", response_model=list[ReportOut])
def list_reports(
    current_user: User = Depends(
        require_role(RoleEnum.student, RoleEnum.attending, RoleEnum.admin)
    ),
    db: Session = Depends(get_db),
) -> list[Report]:
    stmt = (
        select(Report)
        .where(Report.recipient_id == current_user.id)
        .order_by(Report.created_at.desc())
    )
    return list(db.scalars(stmt))


@router.post("/reports/generate", response_model=ReportOut, status_code=201)
def generate_report_now(
    payload: GenerateReportIn,
    current_user: User = Depends(
        require_role(RoleEnum.student, RoleEnum.attending, RoleEnum.admin)
    ),
    db: Session = Depends(get_db),
) -> Report:
    """Generate one user-selected rolling report immediately rather than
    waiting for the worker's next calendar-boundary report.
    """
    now = datetime.now(UTC)
    period_type = ReportPeriodType(payload.period_type)
    period_days = 7 if period_type is ReportPeriodType.weekly else 30
    return generate_periodic_report(
        db,
        current_user,
        period_type=period_type,
        period_start=now - timedelta(days=period_days),
        period_end=now,
        use_ai=payload.output_style == "ai_narrated",
    )


@router.post("/reports/ask", response_model=ReportOut, status_code=201)
def ask_question(
    payload: AskQuestionIn,
    current_user: User = Depends(
        require_role(RoleEnum.student, RoleEnum.attending, RoleEnum.admin)
    ),
    db: Session = Depends(get_db),
) -> Report:
    return answer_ad_hoc_question(db, current_user, payload.question)
