"""roles and identity override

Revision ID: c4a8e2b71f03
Revises: 06c1194d8229
Create Date: 2026-10-12 18:20:00.000000

"""
from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from uuid6 import uuid7


revision: str = "c4a8e2b71f03"
down_revision: Union[str, Sequence[str], None] = "06c1194d8229"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_ROLES = ("accountant", "staff")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "identity_overridden",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    for role_name in _NEW_ROLES:
        _insert_role(role_name)


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM roles WHERE role_name IN ('accountant', 'staff') "
            "AND NOT EXISTS (SELECT 1 FROM users WHERE users.role_id = roles.id)"
        )
    )
    op.drop_column("users", "identity_overridden")


def _insert_role(role_name: str) -> None:
    role_id: UUID = uuid7()
    op.execute(
        sa.text(
            "INSERT INTO roles (id, created_at, updated_at, role_name) "
            "SELECT :id, now(), now(), :role_name "
            "WHERE NOT EXISTS (SELECT 1 FROM roles WHERE role_name = :role_name)"
        ).bindparams(id=role_id, role_name=role_name)
    )
