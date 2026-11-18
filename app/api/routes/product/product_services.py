from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
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
    ReplaceRequest,
    ProductOption,
    ProductRead,
    ProductUpdate,
    RouteStepRead,
    RouteStepWrite,
    RouteWrite,
)
from app.api.routes.raw_material.raw_material_model import RawMaterial
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


DEFAULT_UNITS = (
    "kg",
    "gram",
    "tonne",
    "piece",
    "bundle (12 pcs)",
    "liter",
    "meter",
    "foot",
    "sheet",
    "coil",
)
UNIT_ABBREVIATIONS = {
    "kg": "kg",
    "kilogram": "kg",
    "gram": "g",
    "tonne": "t",
    "piece": "pc",
    "bundle (12 pcs)": "bdl",
    "liter": "L",
    "liters": "L",
    "litre": "L",
    "litres": "L",
    "meter": "m",
    "metre": "m",
    "foot": "ft",
    "feet": "ft",
    "sheet": "sht",
    "coil": "coil",
    "pipe": "pipe",
}


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_default_units(self) -> None:
        rows = list(await self.session.scalars(select(MeasurementUnit)))
        found = {row.name for row in rows}
        changed = False
        for name in DEFAULT_UNITS:
            if name not in found:
                self.session.add(MeasurementUnit(name=name, abbreviation=UNIT_ABBREVIATIONS.get(name)))
                changed = True
        for row in rows:
            if row.abbreviation:
                continue
            abbreviation = UNIT_ABBREVIATIONS.get(row.name.strip().lower())
            if abbreviation:
                row.abbreviation = abbreviation
                changed = True
        if not changed:
            return
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()

    async def list_units(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[MeasurementUnitRead]:
        await self.ensure_default_units()
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

    async def unit_usage(self, unit_id: UUID) -> int:
        products = int(
            await self.session.scalar(
                select(func.count()).select_from(Product).where(Product.measurement_unit_id == unit_id)
            )
            or 0
        )
        materials = int(
            await self.session.scalar(
                select(func.count()).select_from(RawMaterial).where(RawMaterial.measurement_unit_id == unit_id)
            )
            or 0
        )
        return products + materials

    async def delete_unit(self, unit_id: UUID) -> None:
        await get_or_404(self.session, MeasurementUnit, unit_id)
        used = await self.unit_usage(unit_id)
        if used:
            raise HTTPException(
                status_code=409,
                detail=f"{used} goods use this unit. Move them to another unit before removing it.",
            )
        await delete_model(self.session, MeasurementUnit, unit_id)

    async def replace_unit(self, unit_id: UUID, data: ReplaceRequest) -> MeasurementUnitRead:
        await get_or_404(self.session, MeasurementUnit, unit_id)
        if data.replacement_id is not None:
            if data.replacement_id == unit_id:
                raise HTTPException(status_code=400, detail="Pick a different unit")
            replacement = await get_or_404(self.session, MeasurementUnit, data.replacement_id)
        else:
            replacement = MeasurementUnit(
                name=data.temporary_name.strip(),
                detail=(data.detail or "").strip() or None,
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            self.session.add(replacement)
            await self.session.flush()
        await self.session.execute(
            update(Product).where(Product.measurement_unit_id == unit_id).values(measurement_unit_id=replacement.id)
        )
        await self.session.execute(
            update(RawMaterial).where(RawMaterial.measurement_unit_id == unit_id).values(measurement_unit_id=replacement.id)
        )
        await self.session.delete(await get_or_404(self.session, MeasurementUnit, unit_id))
        await commit_or_conflict(self.session)
        await self.session.refresh(replacement)
        return MeasurementUnitRead.model_validate(replacement)

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
        await get_or_404(self.session, ProductCategory, category_id)
        used = int(
            await self.session.scalar(
                select(func.count()).select_from(Product).where(Product.category_id == category_id)
            )
            or 0
        )
        if used:
            raise HTTPException(
                status_code=409,
                detail=f"{used} goods use this category. Move them to another category before removing it.",
            )
        await delete_model(self.session, ProductCategory, category_id)

    async def replace_category(self, category_id: UUID, data: ReplaceRequest) -> ProductCategoryRead:
        await get_or_404(self.session, ProductCategory, category_id)
        if data.replacement_id is not None:
            if data.replacement_id == category_id:
                raise HTTPException(status_code=400, detail="Pick a different category")
            replacement = await get_or_404(self.session, ProductCategory, data.replacement_id)
        else:
            replacement = ProductCategory(
                name=data.temporary_name.strip(),
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            self.session.add(replacement)
            await self.session.flush()
        await self.session.execute(
            update(Product).where(Product.category_id == category_id).values(category_id=replacement.id)
        )
        await self.session.delete(await get_or_404(self.session, ProductCategory, category_id))
        await commit_or_conflict(self.session)
        await self.session.refresh(replacement)
        return ProductCategoryRead.model_validate(replacement)

    async def list_products(
        self, pagination: PaginationParams, *, query: str | None, show_prices: bool, brief: bool = False
    ) -> PaginatedResponse[ProductRead]:
        from app.api.routes.inventory.inventory_model import StockReservation
        from app.api.routes.production.production_model import ProductionJob

        filters = []
        if query and query.strip():
            like = f"%{query.strip()}%"
            filters.append(or_(Product.product_name.ilike(like), Product.sku_number.ilike(like)))
        total_col = func.count().over().label("total")
        if brief:
            statement = select(Product, total_col)
        else:
            held = (
                select(func.coalesce(func.sum(StockReservation.quantity), 0))
                .where(StockReservation.status == "held", StockReservation.product_id == Product.id)
                .correlate(Product)
                .scalar_subquery()
            )
            making = (
                select(func.count())
                .select_from(ProductionJob)
                .where(
                    ProductionJob.product_id == Product.id,  # type: ignore[attr-defined]
                    ProductionJob.status.in_(["pending", "in_progress", "awaiting_approval"]),  # type: ignore[attr-defined]
                )
                .correlate(Product)
                .scalar_subquery()
            )
            statement = select(Product, held.label("held"), making.label("making"), total_col)
        if filters:
            statement = statement.where(*filters)
        rows = (
            await self.session.execute(
                statement.order_by(Product.product_name)
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).all()
        if rows:
            total = int(rows[0].total)
        elif pagination.offset:
            count = select(func.count()).select_from(Product)
            if filters:
                count = count.where(*filters)
            total = int(await self.session.scalar(count) or 0)
        else:
            total = 0
        if brief:
            return to_page(
                [self._priced(ProductRead.model_validate(row[0]), show_prices) for row in rows],
                total,
                pagination,
            )
        return to_page(
            [
                self._present_cached(row[0], Decimal(row.held or 0), bool(row.making), show_prices)
                for row in rows
            ],
            total,
            pagination,
        )

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

    async def replace_route(self, product_id: UUID, data: RouteWrite) -> list[RouteStepRead]:
        await get_or_404(self.session, Product, product_id)
        steps = data.steps
        if steps is None:
            steps = [RouteStepWrite(operation_id=item) for item in data.operation_ids]
        existing = await self.session.scalars(
            select(ProductRouteStep).where(ProductRouteStep.product_id == product_id)
        )
        for row in list(existing):
            await self.session.delete(row)
        saved: list[RouteStepRead] = []
        for index, step in enumerate(steps):
            self.session.add(
                ProductRouteStep(
                    product_id=product_id,
                    operation_id=step.operation_id,
                    position=index,
                    allows_send_out=step.allows_send_out,
                    standard_scrap_percent=step.standard_scrap_percent,
                )
            )
            saved.append(
                RouteStepRead(
                    operation_id=step.operation_id,
                    allows_send_out=step.allows_send_out,
                    standard_scrap_percent=step.standard_scrap_percent,
                )
            )
        await self.session.commit()
        return saved

    async def list_route(self, product_id: UUID) -> list[RouteStepRead]:
        rows = await self.session.scalars(
            select(ProductRouteStep)
            .where(ProductRouteStep.product_id == product_id)
            .order_by(ProductRouteStep.position)
        )
        return [
            RouteStepRead(
                operation_id=row.operation_id,
                allows_send_out=bool(row.allows_send_out),
                standard_scrap_percent=row.standard_scrap_percent,
            )
            for row in rows
        ]

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
        return self._priced(data, show_prices)

    def _present_cached(self, row: Product, held: Decimal, making: bool, show_prices: bool) -> ProductRead:
        from app.api.routes.inventory.inventory_services import _status, qty

        snapshot = _status(qty(row.quantity), held, qty(row.alert_quantity), making)
        data = ProductRead.model_validate(row).model_copy(update={
            "on_hand": snapshot["on_hand"],
            "held": snapshot["held"],
            "available": snapshot["available"],
            "stock_status": snapshot["status"],
        })
        return self._priced(data, show_prices)

    @staticmethod
    def _priced(data: ProductRead, show_prices: bool) -> ProductRead:
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
