from fastapi import HTTPException, status

from app.models.user import User


def require_confirmed_patient(patient: User) -> None:
    """A self-registered patient whose owning-student relationship isn't
    confirmed yet can log in and read their own profile, but can't create
    appointments, waitlist entries, or direct messages until the student
    confirms them via `POST /patients/{id}/confirm`.

    Not a concern for student-initiated patients: `POST /patients` sets
    `owner_confirmed_at` immediately, since the student vouched for them.
    """
    if patient.owner_confirmed_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending confirmation from your student",
        )
