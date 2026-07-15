"""add feedback

Revision ID: 2a25805206c3
Revises: d4e9f2a7b6c1
Create Date: 2026-07-15 15:45:34.009236

New `feedback` table (patient/attending -> student, post-completion) plus
one new NotificationType value for the reminder job. Deliberately no
rating/grade column -- purely qualitative, three guiding-question text
fields (went_well/could_improve required, additional_comments optional).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '2a25805206c3'
down_revision: Union[str, None] = 'd4e9f2a7b6c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notification_type_enum ADD VALUE IF NOT EXISTS 'feedback_reminder'")

    # op.create_table()'s CreateTable DDL does not fire the Enum type's own
    # before_create event, so the enum must be created explicitly first --
    # otherwise this only works on a DB that already happens to have the
    # type from a previous run (masked locally, fails clean on a fresh DB).
    feedback_author_role_enum = postgresql.ENUM(
        'patient', 'attending', name='feedback_author_role_enum'
    )
    feedback_author_role_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'feedback',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('appointment_id', sa.Uuid(), nullable=False),
        sa.Column('student_id', sa.Uuid(), nullable=False),
        sa.Column('author_id', sa.Uuid(), nullable=False),
        sa.Column(
            'author_role',
            postgresql.ENUM(
                'patient', 'attending', name='feedback_author_role_enum', create_type=False
            ),
            nullable=False,
        ),
        sa.Column('went_well', sa.Text(), nullable=False),
        sa.Column('could_improve', sa.Text(), nullable=False),
        sa.Column('additional_comments', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id']),
        sa.ForeignKeyConstraint(['author_id'], ['users.id']),
        sa.ForeignKeyConstraint(['student_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('appointment_id', 'author_id', name='uq_feedback_appointment_author'),
    )
    op.create_index(op.f('ix_feedback_appointment_id'), 'feedback', ['appointment_id'], unique=False)
    op.create_index(op.f('ix_feedback_author_id'), 'feedback', ['author_id'], unique=False)
    op.create_index(op.f('ix_feedback_student_id'), 'feedback', ['student_id'], unique=False)


def downgrade() -> None:
    op.drop_table('feedback')
    op.execute('DROP TYPE IF EXISTS feedback_author_role_enum')
    # Note: the notification_type_enum value added in upgrade() is NOT
    # removed here -- Postgres has no `DROP VALUE` for enum types, same
    # accepted limitation as d4e9f2a7b6c1/c29f7803b629/8c1192899eb3.
