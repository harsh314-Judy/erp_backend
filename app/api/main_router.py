from fastapi import APIRouter

from app.api.routes.attendance.attendance_router import router as attendance_router
from app.api.routes.auth.auth_router import router as auth_router
from app.api.routes.customer.customer_router import router as customer_router
from app.api.routes.health import health_routes
from app.api.routes.operation.operation_router import router as operation_router
from app.api.routes.product.product_router import router as product_router
from app.api.routes.production.production_router import router as production_router
from app.api.routes.purchase_order.purchase_order_router import (
    router as purchase_order_router,
)
from app.api.routes.raw_material.raw_material_router import router as raw_material_router
from app.api.routes.sales.sales_router import router as sales_router
from app.api.routes.supplier.supplier_router import router as supplier_router
from app.api.routes.attachment.attachment_router import router as attachment_router
from app.api.routes.inventory.inventory_router import router as inventory_router
from app.api.routes.invoice.invoice_router import router as invoice_router
from app.api.routes.notification.notification_router import router as notification_router
from app.api.routes.report.report_router import router as report_router
from app.api.routes.settings.settings_router import router as settings_router
from app.api.routes.user.user_router import router as user_router

main_router = APIRouter(prefix="/api")

main_router.include_router(health_routes.router)
main_router.include_router(auth_router)
main_router.include_router(attendance_router)
main_router.include_router(user_router)
main_router.include_router(product_router)
main_router.include_router(raw_material_router)
main_router.include_router(operation_router)
main_router.include_router(production_router)
main_router.include_router(supplier_router)
main_router.include_router(purchase_order_router)
main_router.include_router(customer_router)
main_router.include_router(sales_router)
main_router.include_router(inventory_router)
main_router.include_router(invoice_router)
main_router.include_router(notification_router)
main_router.include_router(attachment_router)
main_router.include_router(settings_router)
main_router.include_router(report_router)
