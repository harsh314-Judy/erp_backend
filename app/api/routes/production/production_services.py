from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import select

from app.api.routes.inventory.inventory_model import StockReservation
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
    JobEvent,
    ProductionJobCreate,
    ProductionJobDetail,
    ProductionJobRead,
    ProductionJobUpdate,
    RequirementUpdate,
    StageComplete,
    StageRead,
    StageRevert,
    VarianceCreate,
    VarianceRead,
)
from app.api.routes.raw_material.raw_material_model import RawMaterial
from app.api.routes.user.user_model import Role, User
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.api.security.permissions import VIEW_ASSIGNED_WORK, role_has
from app.db.repository import commit_or_conflict, get_or_404, to_page


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _person(actor: User) -> str:
    name = " ".join(part for part in (actor.first_name, actor.last_name) if part).strip()
    return name or "User"


def _stamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


_role_names: dict[UUID, tuple[float, str]] = {}


class ProductionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.inventory = InventoryService(session)

    async def _role_name(self, role_id: UUID) -> str:
        import time

        now = time.monotonic()
        hit = _role_names.get(role_id)
        if hit is not None and now - hit[0] < 20:
            return hit[1]
        role = await self.session.get(Role, role_id)
        name = role.role_name if role else ""
        _role_names[role_id] = (now, name)
        return name

    async def list_jobs(
        self, pagination: PaginationParams, actor: User
    ) -> PaginatedResponse[ProductionJobRead]:
        query = (
            select(ProductionJob, Product.product_name, Operation.name)
            .outerjoin(Product, Product.id == ProductionJob.product_id)
            .outerjoin(Operation, Operation.id == ProductionJob.current_operation_id)
            .order_by(ProductionJob.created_at.desc())
        )
        role_name = await self._role_name(actor.role_id)
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
        rows = list((await self.session.execute(query)).all())
        total = len(rows)
        page = rows[pagination.offset : pagination.offset + pagination.page_size]
        rendered = [
            await self._read(job, product_name, operation_name) for job, product_name, operation_name in page
        ]
        return to_page(rendered, total, pagination)

    async def get_job(self, job_id: UUID, actor: User) -> ProductionJobDetail:
        job = await get_or_404(self.session, ProductionJob, job_id)
        await self._assert_visible(job, actor)
        return await self._detail(job)

    async def _summaries(self, jobs: list[ProductionJob]) -> list[ProductionJobRead]:
        if not jobs:
            return []
        product_ids = {job.product_id for job in jobs}
        operation_ids = {job.current_operation_id for job in jobs if job.current_operation_id}
        products = {
            row.id: row
            for row in await self.session.scalars(select(Product).where(Product.id.in_(product_ids)))
        }
        operations = (
            {
                row.id: row
                for row in await self.session.scalars(
                    select(Operation).where(Operation.id.in_(operation_ids))
                )
            }
            if operation_ids
            else {}
        )
        rendered: list[ProductionJobRead] = []
        for job in jobs:
            product = products.get(job.product_id)
            operation = operations.get(job.current_operation_id) if job.current_operation_id else None
            rendered.append(
                await self._read(
                    job,
                    product.product_name if product else None,
                    operation.name if operation else None,
                )
            )
        return rendered

    async def create_job(
        self, data: ProductionJobCreate, actor: User, *, commit: bool = True
    ) -> ProductionJobDetail:
        product = await get_or_404(self.session, Product, data.product_id)
        operation_ids = data.operation_ids or await self._default_route(product.id)
        if not operation_ids:
            raise HTTPException(status_code=400, detail="Choose at least one operation")
        first = await get_or_404(self.session, Operation, operation_ids[0])
        if data.assigned_user_id is not None:
            await get_or_404(self.session, User, data.assigned_user_id)
        job = ProductionJob(
            product_id=product.id,
            current_operation_id=first.id,
            notes=data.notes,
            quantity=qty(data.quantity),
            estimated_minutes=data.estimated_minutes,
            due_at=data.deadline,
            source=data.source,
            source_id=data.source_id,
            created_by_user_id=actor.id,
            raw_material_used={},
            operation_flow={
                str(index): str(operation_id) for index, operation_id in enumerate(operation_ids)
            }
            | ({"deadline_set": True} if data.deadline is not None else {}),
            product_used={},
            raw_material_used_after_production={},
            product_used_after_production={},
        )
        self.session.add(job)
        await self.session.flush()
        self._append_event(job, actor, "created", None, "Job opened")
        for index, operation_id in enumerate(operation_ids):
            managers = await users_for_operation(self.session, operation_id)
            self.session.add(
                ProductionJobStage(
                    job_id=job.id,
                    operation_id=operation_id,
                    position=index,
                    assigned_user_id=data.assigned_user_id
                    or (managers[0] if managers else product.responsible_user_id),
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
        mode = f" ({data.polish_type})" if data.polish_type else ""
        moved = "awaiting approval"
        if upcoming is not None:
            nxt = await self.session.get(Operation, upcoming.operation_id)
            moved = nxt.name if nxt else "the next stage"
        detail = f"Finished {operation.name}{mode} → {moved}"
        if data.notes and data.notes.strip():
            detail = f"{detail}. {data.notes.strip()}"
        self._append_event(job, actor, "advanced", operation.name, detail)
        self.session.add(job)
        await commit_or_conflict(self.session)
        return await self._detail(job)

    async def revert_stage(self, job_id: UUID, data: StageRevert, actor: User) -> ProductionJobDetail:
        job = await get_or_404(self.session, ProductionJob, job_id)
        if job.status not in {"in_progress", "awaiting_approval"}:
            raise HTTPException(status_code=409, detail="This job has no stage to step back to")
        stages = await self._stages(job.id)
        done = [stage for stage in stages if stage.status == "done"]
        if not done:
            raise HTTPException(status_code=409, detail="This job is already on the first stage")
        previous = done[-1]
        active = next((stage for stage in stages if stage.status == "active"), None)
        if active is not None:
            active.status = "pending"
            active.started_at = None
            self.session.add(active)
        operation = await get_or_404(self.session, Operation, previous.operation_id)
        was = previous.polish_type
        previous.status = "active"
        previous.completed_at = None
        previous.polish_type = None
        previous.started_at = _now()
        self.session.add(previous)
        job.status = next_status(job.status, "revert")
        job.current_operation_id = previous.operation_id
        note = data.note.strip()
        detail = f"Stepped back to {operation.name}"
        if was:
            detail = f"{detail} (was {was})"
        detail = f"{detail}. {note}"
        self._append_event(job, actor, "reverted", operation.name, detail)
        self.session.add(job)
        await commit_or_conflict(self.session)
        return await self._detail(job)

    async def update_requirements(
        self, job_id: UUID, data: RequirementUpdate, actor: User
    ) -> ProductionJobDetail:
        job = await get_or_404(self.session, ProductionJob, job_id)
        if job.status not in {"in_progress", "awaiting_approval"}:
            raise HTTPException(status_code=409, detail="Requirements can change only while the job is open")
        inputs = {item.id: item for item in await self._inputs(job.id)}
        changes: list[str] = []
        for line in data.inputs:
            item = inputs.get(line.input_id)
            if item is None:
                raise HTTPException(status_code=404, detail="That material is not on this job")
            new_qty = qty(line.planned_quantity)
            old = qty(item.planned_quantity)
            if new_qty == old:
                continue
            await self._resize_hold(item, old, new_qty)
            item.planned_quantity = new_qty
            self.session.add(item)
            changes.append(f"{await self._input_name(item)} {old} → {new_qty}")
        if not changes:
            raise HTTPException(status_code=400, detail="Nothing changed")
        stage_name = await self._current_stage_name(job)
        detail = f"{data.note.strip()} ({'; '.join(changes)})"
        self._append_event(job, actor, "requirement", stage_name, detail)
        self.session.add(job)
        await commit_or_conflict(self.session)
        return await self._detail(job)

    async def log_variance(self, job_id: UUID, data: VarianceCreate, actor: User) -> ProductionJobDetail:
        job = await get_or_404(self.session, ProductionJob, job_id)
        if job.status not in {"in_progress", "awaiting_approval"}:
            raise HTTPException(status_code=409, detail="Variances are logged while the job is open")
        stage_name = await self._current_stage_name(job)
        used = dict(job.product_used or {})
        lines = list(used.get("lines") or [])
        entry = {
            "at": _now().isoformat(),
            "user_name": _person(actor),
            "kind": data.kind,
            "item_name": data.item_name.strip(),
            "quantity": str(qty(data.quantity)),
            "note": data.note.strip(),
            "stage": stage_name,
        }
        lines.append(entry)
        used["lines"] = lines
        job.product_used = used
        flag_modified(job, "product_used")
        label = {"waste": "Wasted", "extra_used": "Used extra", "extra_made": "Made extra"}[data.kind]
        detail = f"{label} {entry['quantity']} {entry['item_name']} — {entry['note']}"
        self._append_event(job, actor, "variance", stage_name, detail)
        self.session.add(job)
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
        if job.due_at is None:
            job.due_at = job.started_at + timedelta(minutes=job.estimated_minutes)
        stages = await self._stages(job.id)
        if stages:
            stages[0].status = "active"
            stages[0].started_at = job.started_at
            self.session.add(stages[0])
            first = await self.session.get(Operation, stages[0].operation_id)
            self._append_event(
                job,
                actor,
                "started",
                first.name if first else None,
                "Stock held and the first stage opened",
            )
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
        return await self._read(
            job,
            product.product_name if product else None,
            operation.name if operation else None,
        )

    async def _read(
        self, job: ProductionJob, product_name: str | None, operation_name: str | None
    ) -> ProductionJobRead:
        creator = None
        if job.created_by_user_id is not None:
            person = await self.session.get(User, job.created_by_user_id)
            if person is not None:
                creator = _person(person)
        assignee_id = await self._assignee_id(job.id)
        assignee = None
        if assignee_id is not None:
            person = await self.session.get(User, assignee_id)
            if person is not None:
                assignee = _person(person)
        open_job = job.status in {"pending", "in_progress", "awaiting_approval"}
        return ProductionJobRead(
            id=job.id,
            product_id=job.product_id,
            product_name=product_name,
            quantity=job.quantity,
            status=job.status,
            notes=job.notes,
            estimated_minutes=job.estimated_minutes,
            due_at=job.due_at,
            started_at=job.started_at,
            source=job.source,
            overdue=bool(job.due_at and open_job and job.due_at < _now()),
            current_operation_name=operation_name,
            produced_quantity=job.produced_quantity,
            created_at=job.created_at,
            created_by_name=creator,
            assigned_user_id=assignee_id,
            assigned_user_name=assignee,
        )

    async def _assignee_id(self, job_id: UUID) -> UUID | None:
        stages = await self._stages(job_id)
        active = next((stage for stage in stages if stage.status == "active" and stage.assigned_user_id), None)
        if active is not None:
            return active.assigned_user_id
        for stage in stages:
            if stage.assigned_user_id is not None:
                return stage.assigned_user_id
        return None

    async def update_job(self, job_id: UUID, data: ProductionJobUpdate, actor: User) -> ProductionJobDetail:
        job = await get_or_404(self.session, ProductionJob, job_id)
        if job.status in {"completed", "cancelled"}:
            raise HTTPException(status_code=409, detail="A closed job cannot be edited")
        changes = data.model_dump(exclude_unset=True)
        notes: list[str] = []
        if "quantity" in changes and changes["quantity"] is not None:
            job.quantity = qty(changes["quantity"])
            notes.append(f"target {job.quantity}")
        if "notes" in changes:
            job.notes = changes["notes"]
            notes.append("instructions")
        if "estimated_minutes" in changes and changes["estimated_minutes"] is not None:
            job.estimated_minutes = changes["estimated_minutes"]
            notes.append(f"duration {job.estimated_minutes} min")
        if "deadline" in changes:
            job.due_at = changes["deadline"]
            notes.append("deadline" if job.due_at else "deadline cleared")
            flow = dict(job.operation_flow or {})
            reminders = dict(flow.get("reminders") or {})
            reminders.pop("deadline", None)
            flow["reminders"] = reminders
            if job.due_at is None:
                flow.pop("deadline_set", None)
            else:
                flow["deadline_set"] = True
            job.operation_flow = flow
            flag_modified(job, "operation_flow")
        if "assigned_user_id" in changes and changes["assigned_user_id"] is not None:
            await get_or_404(self.session, User, changes["assigned_user_id"])
            for stage in await self._stages(job.id):
                stage.assigned_user_id = changes["assigned_user_id"]
                self.session.add(stage)
            person = await self.session.get(User, changes["assigned_user_id"])
            notes.append(f"assigned to {_person(person)}" if person else "assignee")
        if not notes:
            raise HTTPException(status_code=400, detail="Nothing changed")
        stage_name = await self._current_stage_name(job)
        self._append_event(job, actor, "edited", stage_name, "Edited the job: " + ", ".join(notes))
        self.session.add(job)
        await commit_or_conflict(self.session)
        return await self._detail(job)

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
            events=self._events(job),
            variances=self._variances(job),
        )

    def _append_event(
        self,
        job: ProductionJob,
        actor: User,
        action: str,
        stage: str | None,
        detail: str,
    ) -> None:
        flow = dict(job.operation_flow or {})
        events = list(flow.get("log") or [])
        events.append(
            {
                "at": _now().isoformat(),
                "user_name": _person(actor),
                "action": action,
                "stage": stage,
                "detail": detail,
            }
        )
        flow["log"] = events
        job.operation_flow = flow
        flag_modified(job, "operation_flow")
        self.session.add(job)

    def _events(self, job: ProductionJob) -> list[JobEvent]:
        raw = (job.operation_flow or {}).get("log") or []
        events: list[JobEvent] = []
        if not isinstance(raw, list):
            return events
        for item in raw:
            if not isinstance(item, dict):
                continue
            at = _stamp(item.get("at"))
            if at is None:
                continue
            events.append(
                JobEvent(
                    at=at,
                    user_name=str(item.get("user_name") or "User"),
                    action=str(item.get("action") or "note"),
                    stage=item.get("stage") if isinstance(item.get("stage"), str) else None,
                    detail=str(item.get("detail") or ""),
                )
            )
        events.reverse()
        return events

    def _variances(self, job: ProductionJob) -> list[VarianceRead]:
        raw = (job.product_used or {}).get("lines") or []
        rows: list[VarianceRead] = []
        if not isinstance(raw, list):
            return rows
        for item in raw:
            if not isinstance(item, dict):
                continue
            at = _stamp(item.get("at"))
            if at is None:
                continue
            rows.append(
                VarianceRead(
                    at=at,
                    user_name=str(item.get("user_name") or "User"),
                    kind=str(item.get("kind") or "waste"),
                    item_name=str(item.get("item_name") or "Item"),
                    quantity=str(item.get("quantity") or "0"),
                    note=str(item.get("note") or ""),
                    stage=item.get("stage") if isinstance(item.get("stage"), str) else None,
                )
            )
        rows.reverse()
        return rows

    async def _current_stage_name(self, job: ProductionJob) -> str | None:
        stages = await self._stages(job.id)
        active = next((stage for stage in stages if stage.status == "active"), None)
        target = active or (stages[-1] if stages else None)
        if target is None:
            return None
        operation = await self.session.get(Operation, target.operation_id)
        return operation.name if operation else None

    async def _input_name(self, item: ProductionJobInput) -> str:
        if item.product_id is not None:
            product = await self.session.get(Product, item.product_id)
            return product.product_name if product else "Product"
        if item.raw_material_id is not None:
            material = await self.session.get(RawMaterial, item.raw_material_id)
            return material.name if material else "Material"
        return "Item"

    async def _resize_hold(self, item: ProductionJobInput, old: Decimal, new_qty: Decimal) -> None:
        reservation = None
        if item.reservation_id is not None:
            reservation = await self.session.get(StockReservation, item.reservation_id)
            if reservation is None or reservation.status != "held":
                reservation = None
                item.reservation_id = None
        if reservation is None:
            if new_qty <= 0:
                return
            held = await self.inventory.hold(
                quantity=new_qty,
                source_type="production_job_input",
                source_id=item.id,
                product_id=item.product_id,
                raw_material_id=item.raw_material_id,
            )
            item.reservation_id = held.id
            return
        delta = new_qty - old
        if delta > 0:
            free = await self._free(item)
            if free < delta:
                raise HTTPException(status_code=409, detail="Not enough free stock to raise this requirement")
        if new_qty <= 0:
            await self.inventory.release(reservation.id)
            item.reservation_id = None
            return
        reservation.quantity = new_qty
        self.session.add(reservation)
