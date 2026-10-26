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


class DashboardRead(BaseModel):
    role_name: str
    sales: SalesReport | None = None
    production: ProductionReport | None = None
    low_stock: int = 0
    low_stock_items: list[LowStockItem] = []
    approvals: int = 0
    unpaid_invoices: int = 0
    my_jobs: int = 0
    incoming_shipments: int = 0
