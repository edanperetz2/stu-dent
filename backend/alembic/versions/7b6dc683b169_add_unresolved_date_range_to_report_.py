"""add unresolved date range to report content source

Revision ID: 7b6dc683b169
Revises: dcd36550ac3d
Create Date: 2026-08-01 22:07:06.089813

New ReportContentSource value for the ad-hoc assistant path: a real,
supported question type was classified, but the extracted date-range
phrase wasn't one resolve_date_range() recognizes. Previously this case
was indistinguishable from "no phrase given at all" -- both silently fell
back to a generic 30-day window.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '7b6dc683b169'
down_revision: Union[str, None] = 'dcd36550ac3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE report_content_source_enum ADD VALUE IF NOT EXISTS 'unresolved_date_range'"
    )


def downgrade() -> None:
    # Postgres has no `DROP VALUE` for enum types -- a downgrade past this
    # revision leaves 'unresolved_date_range' in place (same known,
    # accepted limitation as the enum-value additions in
    # c29f7803b629_unify_patients_into_users_role_model.py).
    pass
