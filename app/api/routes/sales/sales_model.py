from enum import Enum
from uuid import UUID

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Text
from sqlmodel import Field

from app.db.base import Entity


class SalesProgress(str, Enum):
    ON_HOLD = "on hold"
    IN_PROGRESS = "in progress"
    DELIVERED = "delivered"
    COMPLETED = "completed"


class Sale(Entity, table=True):
    __tablename__ = "sales"

    customer_id: UUID = Field(
        foreign_key="customers.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    product_id: UUID = Field(
        foreign_key="products.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    product_quantity: int = Field(nullable=False)
    product_gst_override_percentage: int | None = Field(default=None, nullable=True)
    is_gst: bool = Field(default=False, nullable=False)
    bundles: int = Field(default=0, nullable=False)
    progress: SalesProgress = Field(
        default=SalesProgress.ON_HOLD,
        sa_type=SqlEnum(
            SalesProgress,
            name="sales_progress",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    note: str | None = Field(default=None, sa_type=Text, nullable=True)
