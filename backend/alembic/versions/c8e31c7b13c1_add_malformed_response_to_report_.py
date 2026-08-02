"""add malformed_response to report content source

Revision ID: c8e31c7b13c1
Revises: e38fbd1063d6
Create Date: 2026-08-02 09:00:00.000000

New ReportContentSource value for the ad-hoc assistant path: the classify
call to Ollama actually succeeded (unlike a genuinely unreachable model)
but returned something _ClassifyResponse couldn't validate. Previously
this shared the `unavailable` value with the truly-unreachable case, even
though report_assistant.py already showed a distinct message for each --
a viewer had no way to tell "the model is down" from "the model responded
with garbage" from content_source alone.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c8e31c7b13c1'
down_revision: Union[str, None] = 'e38fbd1063d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE report_content_source_enum ADD VALUE IF NOT EXISTS 'malformed_response'"
    )


def downgrade() -> None:
    # Postgres has no `DROP VALUE` for enum types -- a downgrade past this
    # revision leaves 'malformed_response' in place (same known, accepted
    # limitation as the enum-value additions in
    # c29f7803b629_unify_patients_into_users_role_model.py and
    # 7b6dc683b169_add_unresolved_date_range_to_report_.py).
    pass
