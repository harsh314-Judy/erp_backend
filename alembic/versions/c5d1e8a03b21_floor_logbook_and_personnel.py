"""worker profiles, department history, and the floor logbook

Revision ID: c5d1e8a03b21
Revises: b3e9c2a14f70
Create Date: 2026-11-12 23:40:00.000000

"""
from datetime import datetime
from typing import Sequence, Union
from uuid import uuid4
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op


revision: str = "c5d1e8a03b21"
down_revision: Union[str, Sequence[str], None] = "b3e9c2a14f70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_KOLKATA = ZoneInfo("Asia/Kolkata")


def _ist_date(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(_KOLKATA)
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(_KOLKATA)


def upgrade() -> None:
    op.add_column("department_workers", sa.Column("phone", sa.String(length=20), nullable=True))
    op.add_column(
        "department_workers",
        sa.Column("employment_type", sa.String(length=16), server_default="permanent", nullable=False),
    )
    op.add_column("department_workers", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("department_workers", sa.Column("emergency_contact_name", sa.String(length=120), nullable=True))
    op.add_column("department_workers", sa.Column("emergency_contact_phone", sa.String(length=20), nullable=True))

    op.create_table(
        "worker_department_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["worker_id"], ["department_workers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_worker_department_history_operation_id", "worker_department_history", ["operation_id"])
    op.create_index("ix_worker_department_history_worker_id", "worker_department_history", ["worker_id"])

    op.create_table(
        "floor_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("output_product_id", sa.Uuid(), nullable=True),
        sa.Column("output_name", sa.String(length=255), nullable=False),
        sa.Column("output_quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("output_unit", sa.String(length=16), nullable=False),
        sa.Column("input_product_id", sa.Uuid(), nullable=True),
        sa.Column("input_raw_material_id", sa.Uuid(), nullable=True),
        sa.Column("input_name", sa.String(length=255), nullable=True),
        sa.Column("input_quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("input_unit", sa.String(length=16), nullable=True),
        sa.Column("scrap_quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("scrap_unit", sa.String(length=16), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("stage_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["input_product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["input_raw_material_id"], ["raw_materials.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_id"], ["production_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["output_product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["stage_id"], ["production_job_stages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stage_id", name="uq_floor_entries_stage_id"),
    )
    op.create_index("ix_floor_entries_entry_date", "floor_entries", ["entry_date"])
    op.create_index("ix_floor_entries_job_id", "floor_entries", ["job_id"])
    op.create_index("ix_floor_entries_operation_id", "floor_entries", ["operation_id"])
    op.create_index("ix_floor_entries_operation_date", "floor_entries", ["operation_id", "entry_date"])

    op.create_table(
        "floor_entry_workers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("worker_name", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["floor_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_id"], ["department_workers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_id", "worker_id", name="uq_floor_entry_worker"),
    )
    op.create_index("ix_floor_entry_workers_entry_id", "floor_entry_workers", ["entry_id"])
    op.create_index("ix_floor_entry_workers_worker_id", "floor_entry_workers", ["worker_id"])

    bind = op.get_bind()
    now = datetime.now(ZoneInfo("UTC"))
    workers = bind.execute(sa.text("SELECT id, operation_id, created_at FROM department_workers")).mappings()
    for worker in workers:
        started = _ist_date(worker["created_at"]).date()
        bind.execute(
            sa.text(
                """
                INSERT INTO worker_department_history
                    (id, created_at, updated_at, worker_id, operation_id, started_on, ended_on)
                VALUES (:id, :now, :now, :worker_id, :operation_id, :started_on, NULL)
                """
            ),
            {
                "id": uuid4(),
                "now": now,
                "worker_id": worker["id"],
                "operation_id": worker["operation_id"],
                "started_on": started,
            },
        )

    stages = bind.execute(
        sa.text(
            """
            SELECT s.id AS stage_id, s.operation_id, s.worker_id, s.worker_name, s.completed_at,
                   j.id AS job_id, j.quantity, j.product_id, j.created_by_user_id,
                   p.product_name, u.name AS unit_name
            FROM production_job_stages s
            JOIN production_jobs j ON j.id = s.job_id
            LEFT JOIN products p ON p.id = j.product_id
            LEFT JOIN measurement_units u ON u.id = p.measurement_unit_id
            WHERE s.status = 'done'
            """
        )
    ).mappings()
    for stage in stages:
        entry_id = uuid4()
        when = stage["completed_at"] or now
        bind.execute(
            sa.text(
                """
                INSERT INTO floor_entries (
                    id, created_at, updated_at, entry_date, operation_id, output_product_id,
                    output_name, output_quantity, output_unit, scrap_quantity, job_id, stage_id,
                    created_by_user_id
                ) VALUES (
                    :id, :now, :now, :entry_date, :operation_id, :output_product_id,
                    :output_name, :output_quantity, :output_unit, 0, :job_id, :stage_id,
                    :created_by_user_id
                )
                """
            ),
            {
                "id": entry_id,
                "now": now,
                "entry_date": _ist_date(when).date(),
                "operation_id": stage["operation_id"],
                "output_product_id": stage["product_id"],
                "output_name": (stage["product_name"] or "Item")[:255],
                "output_quantity": stage["quantity"],
                "output_unit": ((stage["unit_name"] or "pcs")[:16]),
                "job_id": stage["job_id"],
                "stage_id": stage["stage_id"],
                "created_by_user_id": stage["created_by_user_id"],
            },
        )
        if stage["worker_id"] is not None:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO floor_entry_workers
                        (id, created_at, updated_at, entry_id, worker_id, worker_name)
                    VALUES (:id, :now, :now, :entry_id, :worker_id, :worker_name)
                    """
                ),
                {
                    "id": uuid4(),
                    "now": now,
                    "entry_id": entry_id,
                    "worker_id": stage["worker_id"],
                    "worker_name": (stage["worker_name"] or "Worker")[:120],
                },
            )


def downgrade() -> None:
    op.drop_index("ix_floor_entry_workers_worker_id", table_name="floor_entry_workers")
    op.drop_index("ix_floor_entry_workers_entry_id", table_name="floor_entry_workers")
    op.drop_table("floor_entry_workers")
    op.drop_index("ix_floor_entries_operation_date", table_name="floor_entries")
    op.drop_index("ix_floor_entries_operation_id", table_name="floor_entries")
    op.drop_index("ix_floor_entries_job_id", table_name="floor_entries")
    op.drop_index("ix_floor_entries_entry_date", table_name="floor_entries")
    op.drop_table("floor_entries")
    op.drop_index("ix_worker_department_history_worker_id", table_name="worker_department_history")
    op.drop_index("ix_worker_department_history_operation_id", table_name="worker_department_history")
    op.drop_table("worker_department_history")
    op.drop_column("department_workers", "emergency_contact_phone")
    op.drop_column("department_workers", "emergency_contact_name")
    op.drop_column("department_workers", "address")
    op.drop_column("department_workers", "employment_type")
    op.drop_column("department_workers", "phone")
