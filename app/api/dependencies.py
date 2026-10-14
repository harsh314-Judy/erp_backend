from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from app.api.db_dependency import GarageClientDep, PGSessionDep
from app.api.routes.user.user_model import Role, User
from app.api.routes.auth.auth_services import AuthService
from app.api.routes.customer.customer_services import CustomerService
from app.api.routes.health.health_service import HealthService
from app.api.routes.operation.operation_services import OperationService
from app.api.routes.product.product_services import ProductService
from app.api.routes.production.production_services import ProductionService
from app.api.routes.purchase_order.purchase_order_services import PurchaseOrderService
from app.api.routes.raw_material.raw_material_services import RawMaterialService
from app.api.routes.sales.sales_services import SalesService
from app.api.routes.supplier.supplier_services import SupplierService
from app.api.routes.attachment.attachment_services import AttachmentService
from app.api.routes.inventory.inventory_services import InventoryService
from app.api.routes.invoice.invoice_services import InvoiceService
from app.api.routes.purchase_order.purchase_order_services import PurchaseFlowService
from app.api.routes.report.report_services import ReportService
from app.api.routes.sales.sales_services import SalesOrderService
from app.api.routes.settings.settings_services import SettingsService
from app.api.routes.user.user_services import UserService


async def get_current_user(request: Request, session: PGSessionDep) -> User:
    user_id = getattr(request.state, "user_id", None)
    if not isinstance(user_id, UUID):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is missing or expired",
        )
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is missing or expired",
        )
    return user


async def require_admin(
    session: PGSessionDep,
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    role = await session.get(Role, user.role_id)
    if role is None or role.role_name not in {"admin", "super_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is required",
        )
    return user


def get_health_service(
    pg_session: PGSessionDep,
    garage_client: GarageClientDep,
) -> HealthService:
    return HealthService(pg_session, garage_client)


def get_auth_service(pg_session: PGSessionDep) -> AuthService:
    return AuthService(pg_session)


def get_user_service(pg_session: PGSessionDep) -> UserService:
    return UserService(pg_session)


def get_product_service(pg_session: PGSessionDep) -> ProductService:
    return ProductService(pg_session)


def get_raw_material_service(pg_session: PGSessionDep) -> RawMaterialService:
    return RawMaterialService(pg_session)


def get_operation_service(pg_session: PGSessionDep) -> OperationService:
    return OperationService(pg_session)


def get_production_service(pg_session: PGSessionDep) -> ProductionService:
    return ProductionService(pg_session)


def get_supplier_service(pg_session: PGSessionDep) -> SupplierService:
    return SupplierService(pg_session)


def get_purchase_order_service(pg_session: PGSessionDep) -> PurchaseOrderService:
    return PurchaseOrderService(pg_session)


def get_customer_service(pg_session: PGSessionDep) -> CustomerService:
    return CustomerService(pg_session)


def get_sales_service(pg_session: PGSessionDep) -> SalesService:
    return SalesService(pg_session)


def get_sales_order_service(pg_session: PGSessionDep) -> SalesOrderService:
    return SalesOrderService(pg_session)


def get_inventory_service(pg_session: PGSessionDep) -> InventoryService:
    return InventoryService(pg_session)


def get_invoice_service(pg_session: PGSessionDep) -> InvoiceService:
    return InvoiceService(pg_session)


def get_settings_service(pg_session: PGSessionDep) -> SettingsService:
    return SettingsService(pg_session)


def get_report_service(pg_session: PGSessionDep) -> ReportService:
    return ReportService(pg_session)


def get_purchase_flow_service(pg_session: PGSessionDep) -> PurchaseFlowService:
    return PurchaseFlowService(pg_session)


def get_attachment_service(garage_client: GarageClientDep) -> AttachmentService:
    return AttachmentService(garage_client)


type CurrentUserDep = Annotated[User, Depends(get_current_user)]
type AdminUserDep = Annotated[User, Depends(require_admin)]
type HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
type AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
type UserServiceDep = Annotated[UserService, Depends(get_user_service)]
type ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
type RawMaterialServiceDep = Annotated[RawMaterialService, Depends(get_raw_material_service)]
type OperationServiceDep = Annotated[OperationService, Depends(get_operation_service)]
type ProductionServiceDep = Annotated[ProductionService, Depends(get_production_service)]
type SupplierServiceDep = Annotated[SupplierService, Depends(get_supplier_service)]
type PurchaseOrderServiceDep = Annotated[
    PurchaseOrderService, Depends(get_purchase_order_service)
]
type CustomerServiceDep = Annotated[CustomerService, Depends(get_customer_service)]
type SalesServiceDep = Annotated[SalesService, Depends(get_sales_service)]
type SalesOrderServiceDep = Annotated[SalesOrderService, Depends(get_sales_order_service)]
type InventoryServiceDep = Annotated[InventoryService, Depends(get_inventory_service)]
type InvoiceServiceDep = Annotated[InvoiceService, Depends(get_invoice_service)]
type SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]
type ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]
type PurchaseFlowServiceDep = Annotated[PurchaseFlowService, Depends(get_purchase_flow_service)]
type AttachmentServiceDep = Annotated[AttachmentService, Depends(get_attachment_service)]
