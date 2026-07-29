"""add appointment lifecycle notification types

Revision ID: f2ba3a9ee087
Revises: 2a25805206c3
Create Date: 2026-07-29 13:12:16.997285

No column changes -- two new NotificationType values so the appointment
lifecycle routes (create/accept/approve/reject/cancel) can finally notify
participants, same "add enum value by hand" idiom as d4e9f2a7b6c1.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f2ba3a9ee087'
down_revision: Union[str, None] = '2a25805206c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notification_type_enum ADD VALUE IF NOT EXISTS 'appointment_created'")
    op.execute(
        "ALTER TYPE notification_type_enum ADD VALUE IF NOT EXISTS 'appointment_status_changed'"
    )


def downgrade() -> None:
    # Note: the notification_type_enum values added in upgrade() are NOT
    # removed here -- Postgres has no `DROP VALUE` for enum types, same
    # accepted limitation as d4e9f2a7b6c1/c29f7803b629/8c1192899eb3.
    pass
