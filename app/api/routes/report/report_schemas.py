from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class SalesReport(BaseModel):
    total_orders: int
    pending_orders: int
    total_sales: Decimal | None = None
    gst_sales: Decimal | None = None
    non_gst_sales: Decimal | None = None


class ProductionReport(BaseModel):
    total_jobs: int
    completed_jobs: int
    jobs_in_progress: int
    pending_jobs: int


class LowStockItem(BaseModel):
    kind: str
    id: UUID
    name: str
    on_hand: Decimal
    minimum: Decimal
    product_type: str | None = None


class MachineDown(BaseModel):
    name: str
    operation_name: str


class DashboardRead(BaseModel):
    role_name: str
    sales: SalesReport | None = None
    production: ProductionReport | None = None
    low_stock: int = 0
    low_stock_items: list[LowStockItem] = []
    approvals: int = 0
    unpaid_invoices: int = 0
    unpaid_amount: Decimal | None = None
    late_jobs: int = 0
    open_problems: int = 0
    machines_down: list[MachineDown] = []
    my_jobs: int = 0
    incoming_shipments: int = 0


class DepartmentYield(BaseModel):
    name: str
    good: Decimal
    scrap: Decimal


class LateJob(BaseModel):
    id: UUID
    product_name: str | None = None
    due_at: datetime
    status: str
    current_operation_name: str | None = None


class ShopReport(BaseModel):
    yields: list[DepartmentYield]
    late_jobs: list[LateJob]
    unpaid_count: int
    unpaid_total: Decimal | None = None
