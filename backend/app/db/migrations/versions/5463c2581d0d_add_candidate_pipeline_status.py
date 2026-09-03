"""add candidate pipeline status column

Module 1's candidates table (ported from the resume_ingestion PDD) has no
home for the HR pipeline status (Filtered / Contacted / Responded / Inactive /
Round 1 Scored / Shortlisted / Round 2 Scored / Final Decision) that Module 3
and Module 6 need - see docs/api-contracts/resume_ingestion.md open question 1.

For this POC, Module 1 owns the column directly (option (a) from that doc)
rather than a separate status table, since one team now owns both Module 1
and Module 3.

Revision ID: 5463c2581d0d
Revises: 4f2e9a7c1b3d
Create Date: 2026-09-03

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5463c2581d0d"
down_revision = "4f2e9a7c1b3d"
branch_labels = None
depends_on = None

_STATUSES = (
    "FILTERED",
    "CONTACTED",
    "RESPONDED",
    "INACTIVE",
    "ROUND1_SCORED",
    "SHORTLISTED",
    "ROUND2_SCORED",
    "FINAL_DECISION",
)


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="FILTERED",
            comment="HR pipeline status, shared across Modules 2/3/6. See docs/api-contracts/resume_ingestion.md open question 1.",
        ),
    )
    op.create_check_constraint(
        "ck_candidates_status",
        "candidates",
        "status IN (" + ", ".join(f"'{s}'" for s in _STATUSES) + ")",
    )
    op.create_index("ix_candidates_status", "candidates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_candidates_status", table_name="candidates")
    op.drop_constraint("ck_candidates_status", "candidates", type_="check")
    op.drop_column("candidates", "status")
