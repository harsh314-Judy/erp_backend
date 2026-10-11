from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.purchase_order.purchase_order_model import (
    PurchaseOrderProduct,
    PurchaseOrderRawMaterial,
)
from app.api.routes.purchase_order.purchase_order_schemas import (
    PurchaseOrderProductCreate,
    PurchaseOrderProductRead,
    PurchaseOrderProductUpdate,
    PurchaseOrderRawMaterialCreate,
    PurchaseOrderRawMaterialRead,
    PurchaseOrderRawMaterialUpdate,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.db.repository import (
    create_model,
    delete_model,
    get_or_404,
    list_models,
    to_page,
    update_model,
)


class PurchaseOrderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_material_orders(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[PurchaseOrderRawMaterialRead]:
        rows, total = await list_models(self.session, PurchaseOrderRawMaterial, pagination)
        return to_page(
            [PurchaseOrderRawMaterialRead.model_validate(row) for row in rows],
            total,
            pagination,
        )

    async def get_material_order(self, order_id: UUID) -> PurchaseOrderRawMaterialRead:
        return PurchaseOrderRawMaterialRead.model_validate(
            await get_or_404(self.session, PurchaseOrderRawMaterial, order_id)
        )

    async def create_material_order(
        self, data: PurchaseOrderRawMaterialCreate
    ) -> PurchaseOrderRawMaterialRead:
        row = await create_model(self.session, PurchaseOrderRawMaterial, data)
        return PurchaseOrderRawMaterialRead.model_validate(row)

    async def update_material_order(
        self, order_id: UUID, data: PurchaseOrderRawMaterialUpdate
    ) -> PurchaseOrderRawMaterialRead:
        row = await update_model(self.session, PurchaseOrderRawMaterial, order_id, data)
        return PurchaseOrderRawMaterialRead.model_validate(row)

    async def delete_material_order(self, order_id: UUID) -> None:
        await delete_model(self.session, PurchaseOrderRawMaterial, order_id)

    async def list_product_orders(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[PurchaseOrderProductRead]:
        rows, total = await list_models(self.session, PurchaseOrderProduct, pagination)
        return to_page(
            [PurchaseOrderProductRead.model_validate(row) for row in rows],
            total,
            pagination,
        )

    async def get_product_order(self, order_id: UUID) -> PurchaseOrderProductRead:
        return PurchaseOrderProductRead.model_validate(
            await get_or_404(self.session, PurchaseOrderProduct, order_id)
        )

    async def create_product_order(
        self, data: PurchaseOrderProductCreate
    ) -> PurchaseOrderProductRead:
        row = await create_model(self.session, PurchaseOrderProduct, data)
        return PurchaseOrderProductRead.model_validate(row)

    async def update_product_order(
        self, order_id: UUID, data: PurchaseOrderProductUpdate
    ) -> PurchaseOrderProductRead:
        row = await update_model(self.session, PurchaseOrderProduct, order_id, data)
        return PurchaseOrderProductRead.model_validate(row)

    async def delete_product_order(self, order_id: UUID) -> None:
        await delete_model(self.session, PurchaseOrderProduct, order_id)
