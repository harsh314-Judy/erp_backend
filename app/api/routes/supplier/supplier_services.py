from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.supplier.supplier_model import (
    ProductSupplier,
    RawMaterialSupplier,
    Supplier,
)
from app.api.routes.supplier.supplier_schemas import (
    ProductSupplierCreate,
    ProductSupplierRead,
    ProductSupplierUpdate,
    RawMaterialSupplierCreate,
    RawMaterialSupplierRead,
    RawMaterialSupplierUpdate,
    SupplierCreate,
    SupplierRead,
    SupplierUpdate,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.db.repository import (
    commit_or_conflict,
    create_model,
    delete_model,
    get_or_404,
    list_models,
    to_page,
    update_model,
)


class SupplierService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_suppliers(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[SupplierRead]:
        rows, total = await list_models(self.session, Supplier, pagination)
        return to_page([SupplierRead.model_validate(row) for row in rows], total, pagination)

    async def get_supplier(self, supplier_id: UUID) -> SupplierRead:
        return SupplierRead.model_validate(
            await get_or_404(self.session, Supplier, supplier_id)
        )

    async def create_supplier(self, data: SupplierCreate) -> SupplierRead:
        payload = data.model_dump()
        payload["email"] = data.email.strip().lower()
        row = Supplier.model_validate(payload)
        self.session.add(row)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return SupplierRead.model_validate(row)

    async def update_supplier(self, supplier_id: UUID, data: SupplierUpdate) -> SupplierRead:
        row = await update_model(self.session, Supplier, supplier_id, data)
        return SupplierRead.model_validate(row)

    async def delete_supplier(self, supplier_id: UUID) -> None:
        await delete_model(self.session, Supplier, supplier_id)

    async def list_material_links(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[RawMaterialSupplierRead]:
        rows, total = await list_models(self.session, RawMaterialSupplier, pagination)
        return to_page(
            [RawMaterialSupplierRead.model_validate(row) for row in rows],
            total,
            pagination,
        )

    async def create_material_link(
        self, data: RawMaterialSupplierCreate
    ) -> RawMaterialSupplierRead:
        row = await create_model(self.session, RawMaterialSupplier, data)
        return RawMaterialSupplierRead.model_validate(row)

    async def update_material_link(
        self, link_id: UUID, data: RawMaterialSupplierUpdate
    ) -> RawMaterialSupplierRead:
        row = await update_model(self.session, RawMaterialSupplier, link_id, data)
        return RawMaterialSupplierRead.model_validate(row)

    async def delete_material_link(self, link_id: UUID) -> None:
        await delete_model(self.session, RawMaterialSupplier, link_id)

    async def list_product_links(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[ProductSupplierRead]:
        rows, total = await list_models(self.session, ProductSupplier, pagination)
        return to_page(
            [ProductSupplierRead.model_validate(row) for row in rows], total, pagination
        )

    async def create_product_link(self, data: ProductSupplierCreate) -> ProductSupplierRead:
        row = await create_model(self.session, ProductSupplier, data)
        return ProductSupplierRead.model_validate(row)

    async def update_product_link(
        self, link_id: UUID, data: ProductSupplierUpdate
    ) -> ProductSupplierRead:
        row = await update_model(self.session, ProductSupplier, link_id, data)
        return ProductSupplierRead.model_validate(row)

    async def delete_product_link(self, link_id: UUID) -> None:
        await delete_model(self.session, ProductSupplier, link_id)
