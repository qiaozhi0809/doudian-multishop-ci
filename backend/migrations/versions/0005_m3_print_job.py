"""M3：print_job 打印任务表（data-model 6.2 ⑤-b）

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "print_job",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("waybill_id", sa.Integer, sa.ForeignKey("waybills.id"), nullable=False),
        sa.Column("printer_name", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="queued"),
        sa.Column("result_code", sa.Text),
        sa.Column("result_detail", sa.Text),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("finished_at", sa.Text),
    )
    op.create_index(
        "idx_print_job_waybill", "print_job", ["waybill_id", "created_at"],
    )


def downgrade() -> None:
    raise NotImplementedError("本机单用户应用，不提供降级")
