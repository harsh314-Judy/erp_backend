from typing import Annotated

from fastapi import Depends

from app.api.db_dependency import GarageClientDep, PGSessionDep
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
from app.api.routes.user.user_services import UserService


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
