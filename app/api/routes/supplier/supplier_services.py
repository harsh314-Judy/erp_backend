from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.product.product_model import Product
from app.api.routes.raw_material.raw_material_model import RawMaterial
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

_SUPPLY_KINDS = {"materials", "products", "both"}


class SupplierService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_suppliers(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[SupplierRead]:
        rows, total = await list_models(self.session, Supplier, pagination)
        return to_page(await self._present_many(rows), total, pagination)

    async def get_supplier(self, supplier_id: UUID) -> SupplierRead:
        row = await get_or_404(self.session, Supplier, supplier_id)
        return (await self._present_many([row]))[0]

    async def create_supplier(self, data: SupplierCreate) -> SupplierRead:
        self._check_kind(data.supply_kind, data.raw_material_ids, data.product_ids)
        payload = data.model_dump(exclude={"raw_material_ids", "product_ids"})
        payload["email"] = data.email.strip().lower()
        row = Supplier.model_validate(payload)
        self.session.add(row)
        await self.session.flush()
        await self._replace_material_links(row.id, data.raw_material_ids)
        await self._replace_product_links(row.id, data.product_ids)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return (await self._present_many([row]))[0]

    async def update_supplier(self, supplier_id: UUID, data: SupplierUpdate) -> SupplierRead:
        row = await get_or_404(self.session, Supplier, supplier_id)
        changes = data.model_dump(exclude_unset=True, exclude={"raw_material_ids", "product_ids"})
        if "email" in changes and isinstance(changes["email"], str):
            changes["email"] = changes["email"].strip().lower()
        for key, value in changes.items():
            setattr(row, key, value)
        material_ids = (
            data.raw_material_ids
            if "raw_material_ids" in data.model_fields_set
            else await self._material_ids(row.id)
        )
        product_ids = (
            data.product_ids
            if "product_ids" in data.model_fields_set
            else await self._product_ids(row.id)
        )
        self._check_kind(row.supply_kind, material_ids or [], product_ids or [])
        if "raw_material_ids" in data.model_fields_set:
            await self._replace_material_links(row.id, data.raw_material_ids or [])
        if "product_ids" in data.model_fields_set:
            await self._replace_product_links(row.id, data.product_ids or [])
        self.session.add(row)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return (await self._present_many([row]))[0]

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

    async def _present_many(self, rows: list[Supplier]) -> list[SupplierRead]:
        if not rows:
            return []
        ids = [row.id for row in rows]
        material_rows = list(
            await self.session.scalars(
                select(RawMaterialSupplier).where(RawMaterialSupplier.supplier_id.in_(ids))  # type: ignore[attr-defined]
            )
        )
        product_rows = list(
            await self.session.scalars(
                select(ProductSupplier).where(ProductSupplier.supplier_id.in_(ids))  # type: ignore[attr-defined]
            )
        )
        materials: dict[UUID, list[UUID]] = {row.id: [] for row in rows}
        products: dict[UUID, list[UUID]] = {row.id: [] for row in rows}
        for link in material_rows:
            materials[link.supplier_id].append(link.raw_material_id)
        for link in product_rows:
            products[link.supplier_id].append(link.product_id)
        presented: list[SupplierRead] = []
        for row in rows:
            item = SupplierRead.model_validate(row)
            item.raw_material_ids = materials[row.id]
            item.product_ids = products[row.id]
            presented.append(item)
        return presented

    async def _material_ids(self, supplier_id: UUID) -> list[UUID]:
        rows = await self.session.scalars(
            select(RawMaterialSupplier.raw_material_id).where(
                RawMaterialSupplier.supplier_id == supplier_id
            )
        )
        return list(rows)

    async def _product_ids(self, supplier_id: UUID) -> list[UUID]:
        rows = await self.session.scalars(
            select(ProductSupplier.product_id).where(ProductSupplier.supplier_id == supplier_id)
        )
        return list(rows)

    async def _replace_material_links(self, supplier_id: UUID, material_ids: list[UUID]) -> None:
        existing = list(
            await self.session.scalars(
                select(RawMaterialSupplier).where(RawMaterialSupplier.supplier_id == supplier_id)
            )
        )
        existing_ids = {link.raw_material_id for link in existing}
        wanted = set(material_ids)
        for link in existing:
            if link.raw_material_id in wanted:
                continue
            material = await self.session.get(RawMaterial, link.raw_material_id)
            if material is not None and material.supplier_id == supplier_id:
                material.supplier_id = None
                self.session.add(material)
            await self.session.delete(link)
        await self.session.flush()
        for material_id in wanted - existing_ids:
            material = await get_or_404(self.session, RawMaterial, material_id)
            if material.supplier_id is None:
                material.supplier_id = supplier_id
                self.session.add(material)
            self.session.add(
                RawMaterialSupplier(raw_material_id=material_id, supplier_id=supplier_id)
            )

    async def _replace_product_links(self, supplier_id: UUID, product_ids: list[UUID]) -> None:
        existing = list(
            await self.session.scalars(
                select(ProductSupplier).where(ProductSupplier.supplier_id == supplier_id)
            )
        )
        existing_ids = {link.product_id for link in existing}
        wanted = set(product_ids)
        for link in existing:
            if link.product_id not in wanted:
                await self.session.delete(link)
        await self.session.flush()
        for product_id in wanted - existing_ids:
            await get_or_404(self.session, Product, product_id)
            self.session.add(ProductSupplier(product_id=product_id, supplier_id=supplier_id))

    @staticmethod
    def _check_kind(kind: str, material_ids: list[UUID], product_ids: list[UUID]) -> None:
        if kind not in _SUPPLY_KINDS:
            raise HTTPException(
                status_code=400,
                detail="Choose raw materials, products, or both",
            )
        if kind == "materials" and product_ids:
            raise HTTPException(status_code=400, detail="This supplier only supplies raw materials")
        if kind == "products" and material_ids:
            raise HTTPException(status_code=400, detail="This supplier only supplies products")
