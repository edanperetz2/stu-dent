"""unify patients into users role model

Revision ID: c29f7803b629
Revises: a9ef970f80fd
Create Date: 2026-07-11 13:34:39.816602

Collapses the separate `patients` table into a 4th `role_enum` value on
`users` (see CLAUDE.md). `patients` rows have no path to becoming `users`
rows -- they carry their own primary keys unrelated to any `users.id` --
so this is a destructive schema change for that table, applied against a
freshly wiped dev database rather than a data-preserving migration; it is
not meant to run against a database with real patient data to keep.

The `sa.Column(..., nullable=False)` adds below (notifications.recipient_id,
direct_messages.sender_id) assume the tables are empty for the same reason
-- they would need a backfill step against a non-empty table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c29f7803b629'
down_revision: Union[str, None] = 'a9ef970f80fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New enum values. Not usable within this same transaction for
    # anything beyond a plain column value (fine here -- no rows are
    # written using them below), but Postgres doesn't allow removing an
    # enum value at all, so downgrade() can't cleanly undo these.
    op.execute("ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'patient'")
    op.execute(
        "ALTER TYPE notification_type_enum ADD VALUE IF NOT EXISTS 'patient_registration_request'"
    )

    # Drop the exactly-one-recipient/-sender CheckConstraints up front --
    # they reference the dual columns being dropped below, and autogenerate
    # doesn't detect CHECK constraint changes on its own.
    op.drop_constraint('ck_notifications_exactly_one_recipient', 'notifications', type_='check')
    op.drop_constraint('ck_direct_messages_exactly_one_sender', 'direct_messages', type_='check')

    # Every FK referencing `patients` (plus the paired FKs being collapsed)
    # must go before the table itself is dropped.
    op.drop_constraint(op.f('appointments_patient_id_fkey'), 'appointments', type_='foreignkey')
    op.drop_constraint(op.f('audit_log_actor_patient_id_fkey'), 'audit_log', type_='foreignkey')
    op.drop_constraint(op.f('audit_log_actor_user_id_fkey'), 'audit_log', type_='foreignkey')
    op.drop_constraint(
        op.f('direct_messages_patient_id_fkey'), 'direct_messages', type_='foreignkey'
    )
    op.drop_constraint(
        op.f('direct_messages_sender_user_id_fkey'), 'direct_messages', type_='foreignkey'
    )
    op.drop_constraint(
        op.f('direct_messages_sender_patient_id_fkey'), 'direct_messages', type_='foreignkey'
    )
    op.drop_constraint(
        op.f('notifications_recipient_user_id_fkey'), 'notifications', type_='foreignkey'
    )
    op.drop_constraint(
        op.f('notifications_recipient_patient_id_fkey'), 'notifications', type_='foreignkey'
    )
    op.drop_constraint(
        op.f('waitlist_entries_patient_id_fkey'), 'waitlist_entries', type_='foreignkey'
    )

    op.drop_index(op.f('ix_patients_owner_student_id'), table_name='patients')
    op.drop_table('patients')

    # appointments: patient_id now points at users
    op.create_foreign_key(None, 'appointments', 'users', ['patient_id'], ['id'])

    # audit_log: collapse actor_user_id/actor_patient_id -> actor_id
    op.add_column('audit_log', sa.Column('actor_id', sa.Uuid(), nullable=True))
    op.drop_index(op.f('ix_audit_log_actor_patient_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_actor_user_id'), table_name='audit_log')
    op.create_index(op.f('ix_audit_log_actor_id'), 'audit_log', ['actor_id'], unique=False)
    op.create_foreign_key(None, 'audit_log', 'users', ['actor_id'], ['id'])
    op.drop_column('audit_log', 'actor_patient_id')
    op.drop_column('audit_log', 'actor_user_id')

    # direct_messages: collapse sender_user_id/sender_patient_id -> sender_id;
    # patient_id now points at users
    op.add_column('direct_messages', sa.Column('sender_id', sa.Uuid(), nullable=False))
    op.drop_index(op.f('ix_direct_messages_sender_patient_id'), table_name='direct_messages')
    op.drop_index(op.f('ix_direct_messages_sender_user_id'), table_name='direct_messages')
    op.create_index(
        op.f('ix_direct_messages_sender_id'), 'direct_messages', ['sender_id'], unique=False
    )
    op.create_foreign_key(None, 'direct_messages', 'users', ['sender_id'], ['id'])
    op.create_foreign_key(None, 'direct_messages', 'users', ['patient_id'], ['id'])
    op.drop_column('direct_messages', 'sender_user_id')
    op.drop_column('direct_messages', 'sender_patient_id')

    # notifications: collapse recipient_user_id/recipient_patient_id -> recipient_id
    op.add_column('notifications', sa.Column('recipient_id', sa.Uuid(), nullable=False))
    op.drop_index(op.f('ix_notifications_recipient_patient_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_recipient_user_id'), table_name='notifications')
    op.create_index(
        op.f('ix_notifications_recipient_id'), 'notifications', ['recipient_id'], unique=False
    )
    op.create_foreign_key(None, 'notifications', 'users', ['recipient_id'], ['id'])
    op.drop_column('notifications', 'recipient_user_id')
    op.drop_column('notifications', 'recipient_patient_id')

    # users: four new patient-only columns
    op.add_column('users', sa.Column('owner_student_id', sa.Uuid(), nullable=True))
    op.add_column(
        'users', sa.Column('owner_confirmed_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('users', sa.Column('contact_phone', sa.String(), nullable=True))
    op.add_column(
        'users',
        sa.Column(
            'preferred_time_of_day',
            sa.Enum('morning', 'afternoon', 'evening', name='preferred_time_of_day_enum'),
            nullable=True,
        ),
    )
    op.create_index(op.f('ix_users_owner_student_id'), 'users', ['owner_student_id'], unique=False)
    op.create_foreign_key(None, 'users', 'users', ['owner_student_id'], ['id'])

    # waitlist_entries: patient_id now points at users
    op.create_foreign_key(None, 'waitlist_entries', 'users', ['patient_id'], ['id'])


def downgrade() -> None:
    # Reverse order: undo every column/FK change on the surviving tables
    # first, then recreate `patients`, then wire the FKs back to it.
    # Every constraint below is named explicitly via op.f(...) -- the
    # matching create_foreign_key(None, ...) calls in upgrade() let Postgres
    # auto-name them on create, but Alembic's downgrade then has no real
    # name to drop by (`op.drop_constraint(None, ...)` raises CompileError:
    # "it has no name"). Postgres's own auto-naming convention for an FK is
    # `<table>_<column>_fkey`, which is what op.f() reconstructs here.
    op.drop_constraint(
        op.f('waitlist_entries_patient_id_fkey'), 'waitlist_entries', type_='foreignkey'
    )

    op.drop_constraint(op.f('users_owner_student_id_fkey'), 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_owner_student_id'), table_name='users')
    op.drop_column('users', 'preferred_time_of_day')
    op.drop_column('users', 'contact_phone')
    op.drop_column('users', 'owner_confirmed_at')
    op.drop_column('users', 'owner_student_id')

    op.add_column(
        'notifications',
        sa.Column('recipient_patient_id', sa.UUID(), autoincrement=False, nullable=True),
    )
    op.add_column(
        'notifications',
        sa.Column('recipient_user_id', sa.UUID(), autoincrement=False, nullable=True),
    )
    op.drop_constraint(op.f('notifications_recipient_id_fkey'), 'notifications', type_='foreignkey')
    op.drop_index(op.f('ix_notifications_recipient_id'), table_name='notifications')
    op.create_index(
        op.f('ix_notifications_recipient_user_id'),
        'notifications',
        ['recipient_user_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_notifications_recipient_patient_id'),
        'notifications',
        ['recipient_patient_id'],
        unique=False,
    )
    op.drop_column('notifications', 'recipient_id')

    op.add_column(
        'direct_messages',
        sa.Column('sender_patient_id', sa.UUID(), autoincrement=False, nullable=True),
    )
    op.add_column(
        'direct_messages', sa.Column('sender_user_id', sa.UUID(), autoincrement=False, nullable=True)
    )
    op.drop_constraint(
        op.f('direct_messages_sender_id_fkey'), 'direct_messages', type_='foreignkey'
    )
    op.drop_constraint(
        op.f('direct_messages_patient_id_fkey'), 'direct_messages', type_='foreignkey'
    )
    op.drop_index(op.f('ix_direct_messages_sender_id'), table_name='direct_messages')
    op.create_index(
        op.f('ix_direct_messages_sender_user_id'),
        'direct_messages',
        ['sender_user_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_direct_messages_sender_patient_id'),
        'direct_messages',
        ['sender_patient_id'],
        unique=False,
    )
    op.drop_column('direct_messages', 'sender_id')

    op.add_column(
        'audit_log', sa.Column('actor_user_id', sa.UUID(), autoincrement=False, nullable=True)
    )
    op.add_column(
        'audit_log', sa.Column('actor_patient_id', sa.UUID(), autoincrement=False, nullable=True)
    )
    op.drop_constraint(op.f('audit_log_actor_id_fkey'), 'audit_log', type_='foreignkey')
    op.drop_index(op.f('ix_audit_log_actor_id'), table_name='audit_log')
    op.create_index(
        op.f('ix_audit_log_actor_user_id'), 'audit_log', ['actor_user_id'], unique=False
    )
    op.create_index(
        op.f('ix_audit_log_actor_patient_id'), 'audit_log', ['actor_patient_id'], unique=False
    )
    op.drop_column('audit_log', 'actor_id')

    op.drop_constraint(op.f('appointments_patient_id_fkey'), 'appointments', type_='foreignkey')

    # Recreate `patients` before wiring any FK back to it.
    op.create_table(
        'patients',
        sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('owner_student_id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('full_name', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('contact_phone', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('email', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('hashed_password', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('is_active', sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column(
            'deleted_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True
        ),
        sa.Column(
            'created_at',
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            'preferred_time_of_day',
            # create_type=False: this type already exists in the DB at this
            # point in downgrade() -- it was created for users.preferred_
            # time_of_day back in upgrade(), and dropping that column above
            # doesn't drop the shared enum type itself. Without this,
            # create_table tries to CREATE TYPE again and fails with
            # DuplicateObject.
            postgresql.ENUM(
                'morning',
                'afternoon',
                'evening',
                name='preferred_time_of_day_enum',
                create_type=False,
            ),
            autoincrement=False,
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ['owner_student_id'], ['users.id'], name=op.f('patients_owner_student_id_fkey')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('patients_pkey')),
        sa.UniqueConstraint(
            'email',
            name=op.f('patients_email_key'),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_index(op.f('ix_patients_owner_student_id'), 'patients', ['owner_student_id'], unique=False)

    # Now that `patients` exists again, wire every FK back to it.
    op.create_foreign_key(
        op.f('appointments_patient_id_fkey'), 'appointments', 'patients', ['patient_id'], ['id']
    )
    op.create_foreign_key(
        op.f('audit_log_actor_patient_id_fkey'), 'audit_log', 'patients', ['actor_patient_id'], ['id']
    )
    op.create_foreign_key(
        op.f('audit_log_actor_user_id_fkey'), 'audit_log', 'users', ['actor_user_id'], ['id']
    )
    op.create_foreign_key(
        op.f('direct_messages_patient_id_fkey'),
        'direct_messages',
        'patients',
        ['patient_id'],
        ['id'],
    )
    op.create_foreign_key(
        op.f('direct_messages_sender_user_id_fkey'),
        'direct_messages',
        'users',
        ['sender_user_id'],
        ['id'],
    )
    op.create_foreign_key(
        op.f('direct_messages_sender_patient_id_fkey'),
        'direct_messages',
        'patients',
        ['sender_patient_id'],
        ['id'],
    )
    op.create_foreign_key(
        op.f('notifications_recipient_user_id_fkey'),
        'notifications',
        'users',
        ['recipient_user_id'],
        ['id'],
    )
    op.create_foreign_key(
        op.f('notifications_recipient_patient_id_fkey'),
        'notifications',
        'patients',
        ['recipient_patient_id'],
        ['id'],
    )
    op.create_foreign_key(
        op.f('waitlist_entries_patient_id_fkey'),
        'waitlist_entries',
        'patients',
        ['patient_id'],
        ['id'],
    )

    # Note: the `role_enum`/`notification_type_enum` values added in
    # upgrade() are NOT removed here -- Postgres has no `DROP VALUE` for
    # enum types. A downgrade past this revision leaves those enum values
    # in place (a known, accepted limitation for this project).
    op.create_check_constraint(
        'ck_direct_messages_exactly_one_sender',
        'direct_messages',
        '(sender_user_id IS NOT NULL) != (sender_patient_id IS NOT NULL)',
    )
    op.create_check_constraint(
        'ck_notifications_exactly_one_recipient',
        'notifications',
        '(recipient_user_id IS NOT NULL) != (recipient_patient_id IS NOT NULL)',
    )
