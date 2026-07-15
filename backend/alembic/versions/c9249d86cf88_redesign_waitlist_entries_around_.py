"""redesign waitlist entries around explained conflicts

Revision ID: c9249d86cf88
Revises: 5074bc3483b8
Create Date: 2026-07-14 21:50:11.875268

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c9249d86cf88'
down_revision: Union[str, None] = '5074bc3483b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Dev-only data (same precedent as 5074bc3483b8, d7356797b4cd,
    # c29f7803b629): the waitlist entry shape changed enough (new NOT NULL
    # conflict_resource_types array, a renamed status value) that an
    # in-place ALTER would need a backfill value for existing rows and a
    # Postgres enum-value rename anyway -- a clean drop/recreate is
    # simpler and there's no production data to preserve.
    op.drop_table('waitlist_entries')
    op.execute('DROP TYPE IF EXISTS waitlist_status_enum')

    # op.create_table()'s CreateTable DDL does not fire the Enum type's
    # own before_create event (that only happens via Table.create()/
    # MetaData.create_all()), so the enum must be created explicitly
    # first -- otherwise this only works on a DB that already happens to
    # have the type from a previous run (masked locally, but fails clean
    # on a fresh DB, e.g. in CI).
    waitlist_status_enum = postgresql.ENUM(
        'active', 'booked', 'cancelled', name='waitlist_status_enum'
    )
    waitlist_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'waitlist_entries',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('student_id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('attending_id', sa.Uuid(), nullable=True),
        sa.Column('room_id', sa.Uuid(), nullable=True),
        sa.Column('equipment_id', sa.Uuid(), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('student_confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('conflict_resource_types', sa.ARRAY(sa.Text()), nullable=False),
        sa.Column(
            'status',
            postgresql.ENUM(
                'active', 'booked', 'cancelled', name='waitlist_status_enum', create_type=False
            ),
            nullable=False,
        ),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resulting_appointment_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('end_time > start_time', name='ck_waitlist_entries_time_order'),
        sa.ForeignKeyConstraint(['attending_id'], ['users.id']),
        sa.ForeignKeyConstraint(['equipment_id'], ['equipment.id']),
        sa.ForeignKeyConstraint(['patient_id'], ['users.id']),
        sa.ForeignKeyConstraint(['resulting_appointment_id'], ['appointments.id']),
        sa.ForeignKeyConstraint(['room_id'], ['rooms.id']),
        sa.ForeignKeyConstraint(['student_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_waitlist_entries_attending_id'), 'waitlist_entries', ['attending_id'], unique=False)
    op.create_index(op.f('ix_waitlist_entries_equipment_id'), 'waitlist_entries', ['equipment_id'], unique=False)
    op.create_index(op.f('ix_waitlist_entries_patient_id'), 'waitlist_entries', ['patient_id'], unique=False)
    op.create_index(op.f('ix_waitlist_entries_room_id'), 'waitlist_entries', ['room_id'], unique=False)
    op.create_index(op.f('ix_waitlist_entries_student_id'), 'waitlist_entries', ['student_id'], unique=False)


def downgrade() -> None:
    op.drop_table('waitlist_entries')
    op.execute('DROP TYPE IF EXISTS waitlist_status_enum')

    waitlist_status_enum = postgresql.ENUM(
        'active', 'notified', 'cancelled', name='waitlist_status_enum'
    )
    waitlist_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'waitlist_entries',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('student_id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('attending_id', sa.Uuid(), nullable=True),
        sa.Column('room_id', sa.Uuid(), nullable=True),
        sa.Column('equipment_id', sa.Uuid(), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'status',
            postgresql.ENUM(
                'active', 'notified', 'cancelled', name='waitlist_status_enum', create_type=False
            ),
            nullable=False,
        ),
        sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('end_time > start_time', name='ck_waitlist_entries_time_order'),
        sa.ForeignKeyConstraint(['attending_id'], ['users.id']),
        sa.ForeignKeyConstraint(['equipment_id'], ['equipment.id']),
        sa.ForeignKeyConstraint(['patient_id'], ['users.id']),
        sa.ForeignKeyConstraint(['room_id'], ['rooms.id']),
        sa.ForeignKeyConstraint(['student_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_waitlist_entries_attending_id'), 'waitlist_entries', ['attending_id'], unique=False)
    op.create_index(op.f('ix_waitlist_entries_equipment_id'), 'waitlist_entries', ['equipment_id'], unique=False)
    op.create_index(op.f('ix_waitlist_entries_patient_id'), 'waitlist_entries', ['patient_id'], unique=False)
    op.create_index(op.f('ix_waitlist_entries_room_id'), 'waitlist_entries', ['room_id'], unique=False)
    op.create_index(op.f('ix_waitlist_entries_student_id'), 'waitlist_entries', ['student_id'], unique=False)
