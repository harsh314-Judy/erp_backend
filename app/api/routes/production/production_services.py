from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.inventory.inventory_services import InventoryService, users_for_operation
from app.api.routes.invoice.gst import qty
from app.api.routes.notification.notification_services import notify
from app.api.routes.operation.operation_model import Operation
from app.api.routes.product.product_model import Product, ProductComponent, ProductRouteStep
from app.api.routes.production.job_flow import next_status
from app.api.routes.production.production_model import (
    ProductionJob,
    ProductionJobInput,
    ProductionJobStage,
)
from app.api.routes.production.production_schemas import (
    InputRead,
    JobApprove,
    JobCancel,
    ProductionJobCreate,
    ProductionJobDetail,
    ProductionJobRead,
    StageComplete,
    StageRead,
)
from app.api.routes.raw_material.raw_material_model import RawMaterial
from app.api.routes.user.user_model import Role, User
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.api.security.permissions import VIEW_ASSIGNED_WORK, role_has
from app.db.repository import commit_or_conflict, get_or_404, to_page


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProductionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.inventory = InventoryService(session)

    async def list_jobs(
        self, pagination: PaginationParams, actor: User
    ) -> PaginatedResponse[ProductionJobRead]:
        query = select(ProductionJob).order_by(ProductionJob.created_at.desc())
        role = await self.session.get(Role, actor.role_id)
        role_name = role.role_name if role else ""
        if role_has(role_name, VIEW_ASSIGNED_WORK) and not role_has(role_name, "approve_jobs"):
            if role_name == "staff":
                stage_jobs = await self.session.scalars(
                    select(ProductionJobStage.job_id).where(
                        ProductionJobStage.assigned_user_id == actor.id
                    )
                )
                ids = list(stage_jobs)
                if not ids:
                    return to_page([], 0, pagination)
                query = query.where(ProductionJob.id.in_(ids))  # type: ignore[attr-defined]
        result = await self.session.scalars(query)
        rows = list(result)
        total = len(rows)
        page = rows[pagination.offset : pagination.offset + pagination.page_size]
        return to_page([await self._summary(row) for row in page], total, pagination)

    async def get_job(self, job_id: UUID, actor: User) -> ProductionJobDetail:
        job = await get_or_404(self.session, ProductionJob, job_id)
        await self._assert_visible(job, actor)
        return await self._detail(job)

    async def create_job(
        self, data: ProductionJobCreate, actor: User, *, commit: bool = True
    ) -> ProductionJobDetail:
        product = await get_or_404(self.session, Product, data.product_id)
        operation_ids = data.operation_ids or await self._default_route(product.id)
        if not operation_ids:
            raise HTTPException(status_code=400, detail="Choose at least one operation")
        first = await get_or_404(self.session, Operation, operation_ids[0])
        job = ProductionJob(
            product_id=product.id,
            current_operation_id=first.id,
            notes=data.notes,
            quantity=qty(data.quantity),
            estimated_minutes=data.estimated_minutes,
            source=data.source,
            source_id=data.source_id,
            created_by_user_id=actor.id,
            raw_material_used={},
            operation_flow={str(index): str(operation_id) for index, operation_id in enumerate(operation_ids)},
            product_used={},
            raw_material_used_after_production={},
            product_used_after_production={},
        )
        self.session.add(job)
        await self.session.flush()
        for index, operation_id in enumerate(operation_ids):
            managers = await users_for_operation(self.session, operation_id)
            self.session.add(
                ProductionJobStage(
                    job_id=job.id,
                    operation_id=operation_id,
                    position=index,
                    assigned_user_id=managers[0] if managers else product.responsible_user_id,
                    status="active" if index == 0 else "pending",
                )
            )
        components = list(
            await self.session.scalars(
                select(ProductComponent)
                .where(ProductComponent.product_id == product.id)
                .order_by(ProductComponent.position)
            )
        )
        for component in components:
            planned = qty(component.quantity_per_unit * data.quantity)
            self.session.add(
                ProductionJobInput(
                    job_id=job.id,
                    product_id=component.component_product_id,
                    raw_material_id=component.component_raw_material_id,
                    planned_quantity=planned,
                )
            )
        await self.session.flush()
        await self._try_start(job, actor)
        if commit:
            await commit_or_conflict(self.session)
            await self.session.refresh(job)
        return await self._detail(job)

    async def start_job(self, job_id: UUID, actor: User) -> ProductionJobDetail:
        job = await get_or_404(self.session, ProductionJob, job_id)
        await self._try_start(job, actor, required=True)
        await commit_or_conflict(self.session)
        return await self._detail(job)

    async def complete_stage(
        self, job_id: UUID, stage_id: UUID, data: StageComplete, actor: User
    ) -> ProductionJobDetail:
        job = await get_or_404(self.session, ProductionJob, job_id)
        if job.status != "in_progress":
            raise HTTPException(status_code=409, detail="This job is not in progress")
        stage = await get_or_404(self.session, ProductionJobStage, stage_id)
        if stage.job_id != job.id or stage.status != "active":
            raise HTTPException(status_code=409, detail="This stage is not the active one")
        operation = await get_or_404(self.session, Operation, stage.operation_id)
        if operation.name == "polishing" and data.polish_type not in {"dry", "wet"}:
            raise HTTPException(status_code=400, detail="Polishing needs a dry or wet finish")
        stage.status = "done"
        stage.polish_type = data.polish_type
        stage.notes = data.notes
        stage.completed_at = _now()
        self.session.add(stage)
        stages = await self._stages(job.id)
        upcoming = next((item for item in stages if item.status == "pending"), None)
        if upcoming is None:
            job.status = next_status(job.status, "await_approval")
            self.session.add(job)
            await self._notify_approvers(job)
        else:
            upcoming.status = "active"
            upcoming.started_at = _now()
            job.current_operation_id = upcoming.operation_id
            self.session.add(upcoming)
            self.session.add(job)
            if upcoming.assigned_user_id is not None:
                operation_name = (
                    await self.session.get(Operation, upcoming.operation_id)
                )
                await notify(
                    self.session,
                    [upcoming.assigned_user_id],
                    title="A production stage is ready",
                    body=f"{operation_name.name if operation_name else 'Next stage'} is ready for you.",
                    kind="job_stage",
                    link="/staff",
                )
        await commit_or_conflict(self.session)
        return await self._detail(job)

    async def approve(self, job_id: UUID, data: JobApprove, actor: User) -> ProductionJobDetail:
        job = await get_or_404(self.session, ProductionJob, job_id)
        if job.status != "awaiting_approval":
            raise HTTPException(status_code=409, detail="This job is not waiting for approval")
        await self._apply_actuals(job, data.inputs, actor, consume=True)
        await self.inventory.receive(
            quantity=qty(data.produced_quantity),
            reason="production_output",
            source_type="production_job",
            source_id=job.id,
            user_id=actor.id,
            product_id=job.product_id,
            note="Approved production output",
        )
        job.status = next_status(job.status, "approve")
        job.produced_quantity = qty(data.produced_quantity)
        job.completed_at = _now()
        self.session.add(job)
        await commit_or_conflict(self.session)
        return await self._detail(job)

    async def cancel(self, job_id: UUID, data: JobCancel, actor: User) -> ProductionJobDetail:
        job = await get_or_404(self.session, ProductionJob, job_id)
        event = "cancel"
        job.status = next_status(job.status, event)
        if job.started_at is not None:
            await self._apply_actuals(job, data.inputs, actor, consume=True)
            if data.produced_quantity > 0:
                await self.inventory.receive(
                    quantity=qty(data.produced_quantity),
                    reason="production_output",
                    source_type="production_job",
                    source_id=job.id,
                    user_id=actor.id,
                    product_id=job.product_id,
                    note="Output recorded when the job was cancelled",
                )
        else:
            for item in await self._inputs(job.id):
                if item.reservation_id is not None:
                    await self.inventory.release(item.reservation_id)
        job.cancellation_reason = data.reason.strip()
        job.produced_quantity = qty(data.produced_quantity)
        job.completed_at = _now()
        self.session.add(job)
        await commit_or_conflict(self.session)
        return await self._detail(job)

    async def _try_start(self, job: ProductionJob, actor: User, required: bool = False) -> None:
        if job.status not in {"pending", "in_progress"}:
            raise HTTPException(status_code=409, detail="This job cannot be started")
        if job.status == "in_progress":
            return
        inputs = await self._inputs(job.id)
        shortages: list[str] = []
        for item in inputs:
            free = await self._free(item)
            if free < qty(item.planned_quantity):
                shortages.append(item.id.hex)
        if shortages:
            if required:
                raise HTTPException(
                    status_code=409,
                    detail="Not enough free stock to start this job",
                )
            return
        for item in inputs:
            if qty(item.planned_quantity) <= 0:
                continue
            reservation = await self.inventory.hold(
                quantity=qty(item.planned_quantity),
                source_type="production_job_input",
                source_id=item.id,
                product_id=item.product_id,
                raw_material_id=item.raw_material_id,
            )
            item.reservation_id = reservation.id
            self.session.add(item)
        job.status = next_status("pending", "start")
        job.started_at = _now()
        job.due_at = job.started_at + timedelta(minutes=job.estimated_minutes)
        stages = await self._stages(job.id)
        if stages:
            stages[0].status = "active"
            stages[0].started_at = job.started_at
            self.session.add(stages[0])
            if stages[0].assigned_user_id is not None:
                await notify(
                    self.session,
                    [stages[0].assigned_user_id],
                    title="A production job has started",
                    body="The first stage is assigned to you.",
                    kind="job_stage",
                    link="/staff",
                )
        self.session.add(job)

    async def _apply_actuals(
        self, job: ProductionJob, actuals: list, actor: User, *, consume: bool
    ) -> None:
        by_id = {item.id: item for item in await self._inputs(job.id)}
        seen = set()
        for actual in actuals:
            item = by_id.get(actual.input_id)
            if item is None:
                raise HTTPException(status_code=400, detail="Unknown job input")
            used = qty(actual.actual_quantity)
            waste = qty(actual.wastage_quantity)
            deducted = qty(used + waste)
            if item.reservation_id is not None and deducted > qty(item.planned_quantity):
                raise HTTPException(
                    status_code=400, detail="Use plus wastage is above the held quantity"
                )
            item.actual_quantity = used
            item.wastage_quantity = waste
            self.session.add(item)
            seen.add(item.id)
            if consume and item.reservation_id is not None:
                await self.inventory.consume(
                    item.reservation_id,
                    deducted,
                    user_id=actor.id,
                    source_type="production_job",
                    source_id=job.id,
                    note="Consumed when the job closed",
                )
        if consume:
            for item in by_id.values():
                if item.id not in seen and item.reservation_id is not None:
                    await self.inventory.consume(
                        item.reservation_id,
                        qty(item.planned_quantity),
                        user_id=actor.id,
                        source_type="production_job",
                        source_id=job.id,
                        note="Consumed the planned quantity",
                    )

    async def _free(self, item: ProductionJobInput) -> Decimal:
        if item.product_id is not None:
            product = await self.inventory.lock_product(item.product_id)
            return await self.inventory.available_product(product)
        if item.raw_material_id is not None:
            material = await self.inventory.lock_material(item.raw_material_id)
            return await self.inventory.available_material(material)
        return qty(0)

    async def _default_route(self, product_id: UUID) -> list[UUID]:
        rows = await self.session.scalars(
            select(ProductRouteStep)
            .where(ProductRouteStep.product_id == product_id)
            .order_by(ProductRouteStep.position)
        )
        return [row.operation_id for row in rows]

    async def _stages(self, job_id: UUID) -> list[ProductionJobStage]:
        result = await self.session.scalars(
            select(ProductionJobStage)
            .where(ProductionJobStage.job_id == job_id)
            .order_by(ProductionJobStage.position)
        )
        return list(result)

    async def _inputs(self, job_id: UUID) -> list[ProductionJobInput]:
        result = await self.session.scalars(
            select(ProductionJobInput).where(ProductionJobInput.job_id == job_id)
        )
        return list(result)

    async def _notify_approvers(self, job: ProductionJob) -> None:
        result = await self.session.scalars(select(User))
        approvers: list[UUID] = []
        for user in result:
            role = await self.session.get(Role, user.role_id)
            if role and role_has(role.role_name, "approve_jobs"):
                approvers.append(user.id)
        product = await self.session.get(Product, job.product_id)
        await notify(
            self.session,
            approvers,
            title="A job is waiting for approval",
            body=f"{product.product_name if product else 'A job'} is ready to be checked.",
            kind="job_approval",
            link="/accountant",
        )

    async def _assert_visible(self, job: ProductionJob, actor: User) -> None:
        role = await self.session.get(Role, actor.role_id)
        if role is None or role.role_name != "staff":
            return
        stages = await self._stages(job.id)
        if not any(stage.assigned_user_id == actor.id for stage in stages):
            raise HTTPException(status_code=403, detail="This job is not assigned to you")

    async def _summary(self, job: ProductionJob) -> ProductionJobRead:
        product = await self.session.get(Product, job.product_id)
        operation = await self.session.get(Operation, job.current_operation_id)
        overdue = bool(
            job.due_at and job.status == "in_progress" and job.due_at < _now()
        )
        return ProductionJobRead(
            id=job.id,
            product_id=job.product_id,
            product_name=product.product_name if product else None,
            quantity=job.quantity,
            status=job.status,
            notes=job.notes,
            estimated_minutes=job.estimated_minutes,
            due_at=job.due_at,
            started_at=job.started_at,
            source=job.source,
            overdue=overdue,
            current_operation_name=operation.name if operation else None,
            produced_quantity=job.produced_quantity,
        )

    async def _detail(self, job: ProductionJob) -> ProductionJobDetail:
        summary = await self._summary(job)
        stages: list[StageRead] = []
        for stage in await self._stages(job.id):
            operation = await self.session.get(Operation, stage.operation_id)
            stages.append(
                StageRead.model_validate(stage).model_copy(
                    update={"operation_name": operation.name if operation else None}
                )
            )
        inputs: list[InputRead] = []
        for item in await self._inputs(job.id):
            name = None
            available = None
            if item.product_id is not None:
                product = await self.session.get(Product, item.product_id)
                name = product.product_name if product else None
                if product is not None and job.status == "pending":
                    available = await self.inventory.available_product(product)
            if item.raw_material_id is not None:
                material = await self.session.get(RawMaterial, item.raw_material_id)
                name = material.name if material else None
                if material is not None and job.status == "pending":
                    available = await self.inventory.available_material(material)
            inputs.append(
                InputRead.model_validate(item).model_copy(
                    update={"item_name": name, "available": available}
                )
            )
        return ProductionJobDetail(
            **summary.model_dump(),
            stages=stages,
            inputs=inputs,
            cancellation_reason=job.cancellation_reason,
        )
