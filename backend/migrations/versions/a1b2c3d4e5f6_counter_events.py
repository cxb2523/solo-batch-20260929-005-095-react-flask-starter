"""Add counter events for task idempotency

Revision ID: a1b2c3d4e5f6
Revises: fb060a24643d
Create Date: 2026-10-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'fb060a24643d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint('uq_counter_label', 'counter', ['label'])
    op.create_table(
        'counter_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', sa.String(length=36), nullable=True),
        sa.Column('task_id', sa.String(length=64), nullable=False),
        sa.Column('counter_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['counter_id'], ['counter.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'task_id',
            'counter_id',
            name='uq_counter_event_task_counter'
        )
    )
    op.create_index('ix_counter_event_task_id', 'counter_event', ['task_id'])


def downgrade():
    op.drop_table('counter_event')
    op.drop_constraint('uq_counter_label', 'counter', type_='unique')
