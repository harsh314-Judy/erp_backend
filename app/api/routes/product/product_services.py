from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.product.product_model import MeasurementUnit, Product, ProductCategory
from app.api.routes.product.product_schemas import (
    MeasurementUnitCreate,
    MeasurementUnitRead,
    MeasurementUnitUpdate,
    ProductCategoryCreate,
    ProductCategoryRead,
    ProductCategoryUpdate,
    ProductCreate,
    ProductRead,
    ProductUpdate,
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


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_units(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[MeasurementUnitRead]:
        rows, total = await list_models(self.session, MeasurementUnit, pagination)
        return to_page(
            [MeasurementUnitRead.model_validate(row) for row in rows], total, pagination
        )

    async def create_unit(self, data: MeasurementUnitCreate) -> MeasurementUnitRead:
        row = await create_model(self.session, MeasurementUnit, data)
        return MeasurementUnitRead.model_validate(row)

    async def update_unit(
        self, unit_id: UUID, data: MeasurementUnitUpdate
    ) -> MeasurementUnitRead:
        row = await update_model(self.session, MeasurementUnit, unit_id, data)
        return MeasurementUnitRead.model_validate(row)

    async def delete_unit(self, unit_id: UUID) -> None:
        await delete_model(self.session, MeasurementUnit, unit_id)

    async def list_categories(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[ProductCategoryRead]:
        rows, total = await list_models(self.session, ProductCategory, pagination)
        return to_page(
            [ProductCategoryRead.model_validate(row) for row in rows], total, pagination
        )

    async def create_category(self, data: ProductCategoryCreate) -> ProductCategoryRead:
        row = await create_model(self.session, ProductCategory, data)
        return ProductCategoryRead.model_validate(row)

    async def update_category(
        self, category_id: UUID, data: ProductCategoryUpdate
    ) -> ProductCategoryRead:
        row = await update_model(self.session, ProductCategory, category_id, data)
        return ProductCategoryRead.model_validate(row)

    async def delete_category(self, category_id: UUID) -> None:
        await delete_model(self.session, ProductCategory, category_id)

    async def list_products(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[ProductRead]:
        rows, total = await list_models(self.session, Product, pagination)
        return to_page([ProductRead.model_validate(row) for row in rows], total, pagination)

    async def get_product(self, product_id: UUID) -> ProductRead:
        return ProductRead.model_validate(
            await get_or_404(self.session, Product, product_id)
        )

    async def create_product(self, data: ProductCreate) -> ProductRead:
        row = await create_model(self.session, Product, data)
        return ProductRead.model_validate(row)

    async def update_product(self, product_id: UUID, data: ProductUpdate) -> ProductRead:
        row = await update_model(self.session, Product, product_id, data)
        return ProductRead.model_validate(row)

    async def delete_product(self, product_id: UUID) -> None:
        await delete_model(self.session, Product, product_id)
