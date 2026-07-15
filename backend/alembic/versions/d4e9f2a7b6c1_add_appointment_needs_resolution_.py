"""add appointment_needs_resolution notification type

Revision ID: d4e9f2a7b6c1
Revises: aa01f3e9fe1c
Create Date: 2026-07-15 09:00:00.000000

No column changes -- just a new NotificationType value for the
unresolved-past-appointment nag job. Autogenerate doesn't detect new enum
values on its own (same as the role_enum/notification_type_enum additions
in c29f7803b629 and 8c1192899eb3), so that's added by hand here too.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4e9f2a7b6c1'
down_revision: Union[str, None] = 'aa01f3e9fe1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE notification_type_enum ADD VALUE IF NOT EXISTS "
        "'appointment_needs_resolution'"
    )


def downgrade() -> None:
    # Note: the notification_type_enum value added in upgrade() is NOT
    # removed here -- Postgres has no `DROP VALUE` for enum types, same
    # accepted limitation as c29f7803b629/8c1192899eb3.
    pass
