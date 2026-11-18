"""unit abbreviation and weight per piece

Revision ID: e9b4c32d7a10
Revises: d8f3a21c6b09
Create Date: 2026-11-18 14:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e9b4c32d7a10"
down_revision: Union[str, Sequence[str], None] = "d8f3a21c6b09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ABBREVIATIONS = {
    "kg": "kg",
    "kilogram": "kg",
    "gram": "g",
    "tonne": "t",
    "piece": "pc",
    "bundle (12 pcs)": "bdl",
    "liter": "L",
    "liters": "L",
    "litre": "L",
    "litres": "L",
    "meter": "m",
    "metre": "m",
    "foot": "ft",
    "feet": "ft",
    "sheet": "sht",
    "coil": "coil",
    "pipe": "pipe",
}


def upgrade() -> None:
    op.add_column("measurement_units", sa.Column("abbreviation", sa.String(length=16), nullable=True))
    op.add_column("products", sa.Column("weight_per_piece", sa.Numeric(14, 3), nullable=True))
    connection = op.get_bind()
    for name, abbreviation in ABBREVIATIONS.items():
        connection.execute(
            sa.text(
                "UPDATE measurement_units SET abbreviation = :abbreviation "
                "WHERE lower(name) = :name AND abbreviation IS NULL"
            ),
            {"abbreviation": abbreviation, "name": name},
        )


def downgrade() -> None:
    op.drop_column("products", "weight_per_piece")
    op.drop_column("measurement_units", "abbreviation")
