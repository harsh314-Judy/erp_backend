"""editable catalog names and temporary replacements

Revision ID: d8f3a21c6b09
Revises: c7e2a91b4d08
Create Date: 2026-11-18 14:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d8f3a21c6b09"
down_revision: Union[str, Sequence[str], None] = "c7e2a91b4d08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("measurement_units", sa.Column("detail", sa.Text(), nullable=True))
    op.add_column("measurement_units", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("product_categories", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("raw_material_categories", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("raw_material_categories", "expires_at")
    op.drop_column("product_categories", "expires_at")
    op.drop_column("measurement_units", "expires_at")
    op.drop_column("measurement_units", "detail")
