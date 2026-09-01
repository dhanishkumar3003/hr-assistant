"""add email_outreach tables

Revision ID: c1a5e0f9b3d2
Revises: 9336eb4da9d1
Create Date: 2026-08-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1a5e0f9b3d2'
down_revision = '9336eb4da9d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('email_outreach_emails',
    sa.Column('email_id', sa.Integer(), nullable=False),
    sa.Column('candidate_id', sa.String(length=36), nullable=True),
    sa.Column('token', sa.String(length=64), nullable=False),
    sa.Column('round_id', sa.String(length=64), nullable=True),
    sa.Column('round_number', sa.Integer(), nullable=True),
    sa.Column('message_id', sa.String(length=255), nullable=True),
    sa.Column('candidate_email', sa.String(length=255), nullable=False),
    sa.Column('candidate_name', sa.String(length=255), nullable=True),
    sa.Column('job_role', sa.String(length=255), nullable=True),
    sa.Column('company_name', sa.String(length=255), nullable=True),
    sa.Column('hr_name', sa.String(length=255), nullable=True),
    sa.Column('hr_designation', sa.String(length=255), nullable=True),
    sa.Column('hr_email', sa.String(length=255), nullable=True),
    sa.Column('recipient_email', sa.String(length=255), nullable=False),
    sa.Column('subject', sa.String(length=500), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('email_type', sa.String(length=50), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('approved_at', sa.DateTime(), nullable=True),
    sa.Column('approved_by', sa.String(length=255), nullable=True),
    sa.Column('sent_at', sa.DateTime(), nullable=True),
    sa.Column('response_due_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('resend_count', sa.Integer(), nullable=False),
    sa.Column('last_resent_at', sa.DateTime(), nullable=True),
    sa.Column('next_resend_at', sa.DateTime(), nullable=True),
    sa.Column('resend_reason', sa.String(length=100), nullable=True),
    sa.Column('is_resend', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('email_id'),
    sa.UniqueConstraint('message_id'),
    sa.UniqueConstraint('token')
    )
    op.create_index(
        op.f('ix_email_outreach_emails_candidate_id'),
        'email_outreach_emails', ['candidate_id'], unique=False,
    )
    op.create_table('email_outreach_candidate_responses',
    sa.Column('response_id', sa.Integer(), nullable=False),
    sa.Column('email_id', sa.Integer(), nullable=False),
    sa.Column('subject', sa.String(length=500), nullable=False),
    sa.Column('response_body', sa.Text(), nullable=False),
    sa.Column('intent', sa.String(length=100), nullable=True),
    sa.Column('intent_percentage', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('classification_source', sa.String(length=30), nullable=True),
    sa.Column('received_at', sa.DateTime(), nullable=False),
    sa.Column('analyzed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('candidate_requested_date', sa.DateTime(), nullable=True),
    sa.Column('trigger_date', sa.DateTime(), nullable=True),
    sa.Column('follow_up_required', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['email_id'], ['email_outreach_emails.email_id'], ),
    sa.PrimaryKeyConstraint('response_id')
    )


def downgrade() -> None:
    op.drop_table('email_outreach_candidate_responses')
    op.drop_index(op.f('ix_email_outreach_emails_candidate_id'), table_name='email_outreach_emails')
    op.drop_table('email_outreach_emails')
