from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.department.department_model import DepartmentWorker
from app.api.routes.department.department_schemas import (
    DepartmentActive,
    DepartmentInput,
    DepartmentRead,
    DepartmentRecent,
    WorkerCount,
    WorkerPatch,
    WorkerRead,
    WorkerWrite,
)
from app.api.routes.operation.operation_model import Operation
from app.api.routes.product.product_model import Product
from app.api.routes.production.production_model import (
    ProductionJob,
    ProductionJobInput,
    ProductionJobStage,
)
from app.api.routes.raw_material.raw_material_model import RawMaterial
from app.db.repository import commit_or_conflict, get_or_404

_ROUTE = ["cutting", "shaping", "assembly", "polishing", "coloring", "packaging"]


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


class DepartmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_workers(self) -> list[WorkerRead]:
        rows = await self.session.scalars(
            select(DepartmentWorker)
            .where(DepartmentWorker.active.is_(True))
            .order_by(DepartmentWorker.name)
        )
        return [
            WorkerRead(id=row.id, operation_id=row.operation_id, name=row.name, active=row.active)
            for row in rows
        ]

    async def add_worker(self, operation_id: UUID, data: WorkerWrite) -> WorkerRead:
        await get_or_404(self.session, Operation, operation_id)
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Enter a name")
        existing = await self._match(operation_id, name)
        if existing is not None:
            existing.active = True
            existing.name = name
            self.session.add(existing)
            await commit_or_conflict(self.session)
            return WorkerRead(
                id=existing.id, operation_id=existing.operation_id, name=existing.name, active=True
            )
        row = DepartmentWorker(operation_id=operation_id, name=name, active=True)
        self.session.add(row)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return WorkerRead(id=row.id, operation_id=row.operation_id, name=row.name, active=row.active)

    async def update_worker(self, worker_id: UUID, data: WorkerPatch) -> WorkerRead:
        row = await get_or_404(self.session, DepartmentWorker, worker_id)
        if data.name is not None:
            name = data.name.strip()
            if not name:
                raise HTTPException(status_code=400, detail="Enter a name")
            other = await self._match(row.operation_id, name)
            if other is not None and other.id != row.id:
                raise HTTPException(status_code=409, detail="That name is already in this department")
            row.name = name
        if data.active is not None:
            row.active = data.active
        self.session.add(row)
        await commit_or_conflict(self.session)
        return WorkerRead(id=row.id, operation_id=row.operation_id, name=row.name, active=row.active)

    async def overview(self) -> list[DepartmentRead]:
        operations = list(await self.session.scalars(select(Operation)))
        operations.sort(key=lambda item: (_ROUTE.index(item.name.lower()) if item.name.lower() in _ROUTE else 99, item.name))
        workers = list(await self.session.scalars(select(DepartmentWorker).order_by(DepartmentWorker.name)))
        since = _now() - timedelta(days=7)
        active_rows = (
            await self.session.execute(
                select(ProductionJobStage, ProductionJob, Product.product_name)
                .join(ProductionJob, ProductionJob.id == ProductionJobStage.job_id)
                .outerjoin(Product, Product.id == ProductionJob.product_id)
                .where(ProductionJobStage.status == "active", ProductionJob.status == "in_progress")
            )
        ).all()
        recent_rows = (
            await self.session.execute(
                select(ProductionJobStage, ProductionJob, Product.product_name)
                .join(ProductionJob, ProductionJob.id == ProductionJobStage.job_id)
                .outerjoin(Product, Product.id == ProductionJob.product_id)
                .where(ProductionJobStage.status == "done", ProductionJobStage.completed_at >= since)
                .order_by(ProductionJobStage.completed_at.desc())
            )
        ).all()
        job_ids = {job.id for _, job, _ in active_rows}
        inputs: dict[UUID, list[DepartmentInput]] = {}
        if job_ids:
            material_rows = list(
                await self.session.scalars(
                    select(ProductionJobInput).where(ProductionJobInput.job_id.in_(job_ids))  # type: ignore[attr-defined]
                )
            )
            product_ids = {row.product_id for row in material_rows if row.product_id}
            material_ids = {row.raw_material_id for row in material_rows if row.raw_material_id}
            product_names = {
                row.id: row.product_name
                for row in await self.session.scalars(select(Product).where(Product.id.in_(product_ids)))  # type: ignore[attr-defined]
            } if product_ids else {}
            material_names = {
                row.id: row.name
                for row in await self.session.scalars(select(RawMaterial).where(RawMaterial.id.in_(material_ids)))  # type: ignore[attr-defined]
            } if material_ids else {}
            for row in material_rows:
                name = product_names.get(row.product_id) if row.product_id else material_names.get(row.raw_material_id)
                inputs.setdefault(row.job_id, []).append(
                    DepartmentInput(item_name=name or "Item", planned_quantity=row.planned_quantity)
                )
        by_operation: dict[UUID, DepartmentRead] = {}
        for operation in operations:
            people = [
                WorkerRead(id=row.id, operation_id=row.operation_id, name=row.name, active=row.active)
                for row in workers
                if row.operation_id == operation.id and row.active
            ]
            by_operation[operation.id] = DepartmentRead(
                operation_id=operation.id,
                name=operation.name,
                workers=people,
                active=[],
                recent=[],
                per_worker=[],
            )
        for stage, job, product_name in active_rows:
            bucket = by_operation.get(stage.operation_id)
            if bucket is None:
                continue
            bucket.active.append(
                DepartmentActive(
                    job_id=job.id,
                    product_name=product_name,
                    quantity=job.quantity,
                    started_at=stage.started_at,
                    due_at=job.due_at,
                    inputs=inputs.get(job.id, []),
                )
            )
        counts: dict[UUID, dict[str, int]] = {}
        for stage, job, product_name in recent_rows:
            bucket = by_operation.get(stage.operation_id)
            if bucket is None:
                continue
            if len(bucket.recent) < 10:
                bucket.recent.append(
                    DepartmentRecent(
                        worker_name=stage.worker_name,
                        product_name=product_name,
                        quantity=job.quantity,
                        completed_at=stage.completed_at,
                        polish_type=stage.polish_type,
                    )
                )
            label = stage.worker_name or "Unnamed"
            counts.setdefault(stage.operation_id, {})
            counts[stage.operation_id][label] = counts[stage.operation_id].get(label, 0) + 1
        for operation_id, names in counts.items():
            by_operation[operation_id].per_worker = [
                WorkerCount(name=name, stages=total)
                for name, total in sorted(names.items(), key=lambda item: (-item[1], item[0]))
            ]
        return list(by_operation.values())

    async def _match(self, operation_id: UUID, name: str) -> DepartmentWorker | None:
        return await self.session.scalar(
            select(DepartmentWorker).where(
                DepartmentWorker.operation_id == operation_id,
                func.lower(DepartmentWorker.name) == name.lower(),
            )
        )
