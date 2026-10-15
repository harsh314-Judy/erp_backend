from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, or_, select

from app.api.routes.inventory.inventory_services import InventoryService
from app.api.routes.product.product_model import (
    MeasurementUnit,
    Product,
    ProductCategory,
    ProductComponent,
    ProductRouteStep,
)
from app.api.routes.product.product_schemas import (
    ComponentRead,
    ComponentWrite,
    MeasurementUnitCreate,
    MeasurementUnitRead,
    MeasurementUnitUpdate,
    ProductCategoryCreate,
    ProductCategoryRead,
    ProductCategoryUpdate,
    ProductCreate,
    ProductOption,
    ProductRead,
    ProductUpdate,
)
from app.api.routes.raw_material.raw_material_model import RawMaterial
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
        self, pagination: PaginationParams, *, query: str | None, show_prices: bool
    ) -> PaginatedResponse[ProductRead]:
        statement = select(Product)
        count = select(func.count()).select_from(Product)
        if query:
            like = f"%{query.strip()}%"
            statement = statement.where(
                or_(Product.product_name.ilike(like), Product.sku_number.ilike(like))
            )
            count = count.where(or_(Product.product_name.ilike(like), Product.sku_number.ilike(like)))
        total = int(await self.session.scalar(count) or 0)
        result = await self.session.scalars(
            statement.order_by(Product.product_name)
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
        items = [await self._present(row, show_prices) for row in result]
        return to_page(items, total, pagination)

    async def options(self, query: str | None) -> list[ProductOption]:
        statement = select(Product).order_by(Product.product_name).limit(30)
        if query:
            like = f"%{query.strip()}%"
            statement = statement.where(
                or_(Product.product_name.ilike(like), Product.sku_number.ilike(like))
            )
        rows = await self.session.scalars(statement)
        return [ProductOption.model_validate(row) for row in rows]

    async def get_product(self, product_id: UUID, *, show_prices: bool) -> ProductRead:
        return await self._present(
            await get_or_404(self.session, Product, product_id), show_prices
        )

    async def create_product(self, data: ProductCreate, *, show_prices: bool) -> ProductRead:
        self._check_type(data.product_type)
        row = await create_model(self.session, Product, data)
        return await self._present(row, show_prices)

    async def update_product(
        self, product_id: UUID, data: ProductUpdate, *, show_prices: bool
    ) -> ProductRead:
        if data.product_type is not None:
            self._check_type(data.product_type)
        row = await update_model(self.session, Product, product_id, data)
        return await self._present(row, show_prices)

    async def delete_product(self, product_id: UUID) -> None:
        await delete_model(self.session, Product, product_id)

    async def replace_route(self, product_id: UUID, operation_ids: list[UUID]) -> list[UUID]:
        await get_or_404(self.session, Product, product_id)
        existing = await self.session.scalars(
            select(ProductRouteStep).where(ProductRouteStep.product_id == product_id)
        )
        for row in list(existing):
            await self.session.delete(row)
        for index, operation_id in enumerate(operation_ids):
            self.session.add(
                ProductRouteStep(
                    product_id=product_id, operation_id=operation_id, position=index
                )
            )
        await self.session.commit()
        return operation_ids

    async def list_route(self, product_id: UUID) -> list[UUID]:
        rows = await self.session.scalars(
            select(ProductRouteStep)
            .where(ProductRouteStep.product_id == product_id)
            .order_by(ProductRouteStep.position)
        )
        return [row.operation_id for row in rows]

    async def replace_recipe(
        self, product_id: UUID, items: list[ComponentWrite]
    ) -> list[ComponentRead]:
        await get_or_404(self.session, Product, product_id)
        existing = await self.session.scalars(
            select(ProductComponent).where(ProductComponent.product_id == product_id)
        )
        for row in list(existing):
            await self.session.delete(row)
        await self.session.flush()
        created: list[ProductComponent] = []
        for index, item in enumerate(items):
            row = ProductComponent(
                product_id=product_id,
                component_product_id=item.component_product_id,
                component_raw_material_id=item.component_raw_material_id,
                quantity_per_unit=item.quantity_per_unit,
                position=index,
            )
            self.session.add(row)
            created.append(row)
        await self.session.commit()
        for row in created:
            await self.session.refresh(row)
        return [await self._component(row) for row in created]

    async def list_recipe(self, product_id: UUID) -> list[ComponentRead]:
        rows = await self.session.scalars(
            select(ProductComponent)
            .where(ProductComponent.product_id == product_id)
            .order_by(ProductComponent.position)
        )
        return [await self._component(row) for row in rows]

    async def _present(self, row: Product, show_prices: bool) -> ProductRead:
        snapshot = await InventoryService(self.session).stock_snapshot(row)
        data = ProductRead.model_validate(row).model_copy(update={
            "on_hand": snapshot["on_hand"],
            "held": snapshot["held"],
            "available": snapshot["available"],
            "stock_status": snapshot["status"],
        })
        if not show_prices:
            data.sale_price_without_gst = None
        return data

    async def _component(self, row: ProductComponent) -> ComponentRead:
        name = None
        if row.component_product_id is not None:
            product = await self.session.get(Product, row.component_product_id)
            name = product.product_name if product else None
        if row.component_raw_material_id is not None:
            material = await self.session.get(RawMaterial, row.component_raw_material_id)
            name = material.name if material else None
        return ComponentRead(
            id=row.id,
            position=row.position,
            component_product_id=row.component_product_id,
            component_raw_material_id=row.component_raw_material_id,
            quantity_per_unit=row.quantity_per_unit,
            item_name=name,
        )

    @staticmethod
    def _check_type(value: str) -> None:
        if value not in {"manufactured", "purchased", "both"}:
            raise HTTPException(
                status_code=400,
                detail="Product type must be manufactured, purchased, or both",
            )
