"""store the generated invoice pdf on the invoice

Revision ID: e7a1c4b92d10
Revises: c3e1a9b4d2f6
Create Date: 2026-10-28 15:20:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e7a1c4b92d10"
down_revision: Union[str, Sequence[str], None] = "c3e1a9b4d2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("pdf_attachment_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_invoices_pdf_attachment_id",
        "invoices",
        "attachments",
        ["pdf_attachment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_invoices_pdf_attachment_id", "invoices", type_="foreignkey")
    op.drop_column("invoices", "pdf_attachment_id")
