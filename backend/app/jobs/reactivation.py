from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.equipment import Equipment
from app.models.room import Room


def reactivate_expired_deactivations(db: Session) -> int:
    """Auto-reactivate rooms/equipment whose scheduled deactivation window
    (`inactive_until`) has passed -- the admin opted into a time-limited
    deactivation rather than an indefinite one, so this is what actually
    makes that limit take effect. Commits per row so one bad row doesn't
    block the rest of the batch, same convention as jobs/expiry.py.
    """
    now = datetime.now(UTC)
    reactivated = 0

    for model in (Room, Equipment):
        candidates = list(
            db.scalars(
                select(model).where(
                    model.is_active.is_(False),
                    model.inactive_until.is_not(None),
                    model.inactive_until <= now,
                )
            )
        )
        for resource in candidates:
            resource.is_active = True
            resource.inactive_until = None
            db.commit()
            reactivated += 1

    return reactivated
