from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from app.db.base import Entity


class DepartmentWorker(Entity, table=True):
    __tablename__ = "department_workers"
    __table_args__ = (UniqueConstraint("operation_id", "name", name="uq_department_worker_name"),)

    operation_id: UUID = Field(
        foreign_key="operations.id", nullable=False, index=True, ondelete="CASCADE"
    )
    name: str = Field(max_length=120, nullable=False)
    active: bool = Field(default=True, nullable=False)
