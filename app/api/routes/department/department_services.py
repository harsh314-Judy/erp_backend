from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.department.department_model import DepartmentWorker, WorkerDepartmentHistory
from app.api.routes.department.department_schemas import (
    AssignedDepartment,
    DepartmentActive,
    DepartmentInput,
    DepartmentMachine,
    DepartmentRead,
    DepartmentRecent,
    DeskSend,
    OutsideOpen,
    UnitTotal,
    WorkerCount,
    WorkerPatch,
    WorkerRead,
    WorkerWrite,
)
from app.api.routes.floor.floor_aggregate import FloorFact, department_rollup, people_rollup
from app.api.routes.floor.floor_model import FloorEntry, FloorEntryWorker
from app.api.routes.operation.operation_model import Operation, UserOperation
from app.api.routes.product.product_model import Product
from app.api.routes.production.production_model import (
    ProductionJob,
    ProductionJobInput,
    ProductionJobStage,
)
from app.api.routes.raw_material.raw_material_model import RawMaterial
from app.db.repository import commit_or_conflict, get_or_404

_ROUTE = ["cutting", "shaping", "assembly", "polishing", "coloring", "packaging"]
_KOLKATA = ZoneInfo("Asia/Kolkata")


def _today() -> date:
    return datetime.now(_KOLKATA).date()


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _amounts(bucket: dict[str, Decimal]) -> list[UnitTotal]:
    return [UnitTotal(unit=unit, quantity=amount) for unit, amount in sorted(bucket.items()) if amount != 0]


class DepartmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_workers(self, *, include_inactive: bool, reveal: bool, wages: bool = False) -> list[WorkerRead]:
        query = select(DepartmentWorker, Operation.name).join(Operation, Operation.id == DepartmentWorker.operation_id)
        if not include_inactive:
            query = query.where(DepartmentWorker.active.is_(True))
        rows = await self.session.execute(query.order_by(DepartmentWorker.name))
        return [_worker_read(worker, name, reveal, wages) for worker, name in rows]

    async def add_worker(self, operation_id: UUID, data: WorkerWrite, *, reveal: bool, wages: bool = False) -> WorkerRead:
        operation = await get_or_404(self.session, Operation, operation_id)
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Enter a name")
        existing = await self._match(operation_id, name)
        if existing is not None:
            existing.active = True
            existing.name = name
            self._apply_profile(existing, data)
            _apply_wages(existing, data.wage_kind, data.wage_amount, wages)
            self.session.add(existing)
            await self._ensure_history(existing)
            await commit_or_conflict(self.session)
            return _worker_read(existing, operation.name, reveal, wages)
        row = DepartmentWorker(operation_id=operation_id, name=name, active=True)
        self._apply_profile(row, data)
        _apply_wages(row, data.wage_kind, data.wage_amount, wages)
        self.session.add(row)
        await self.session.flush()
        self.session.add(
            WorkerDepartmentHistory(worker_id=row.id, operation_id=operation_id, started_on=_today())
        )
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return _worker_read(row, operation.name, reveal, wages)

    async def update_worker(self, worker_id: UUID, data: WorkerPatch, *, reveal: bool, wages: bool = False) -> WorkerRead:
        row = await get_or_404(self.session, DepartmentWorker, worker_id)
        changes = data.model_dump(exclude_unset=True)
        target_operation = changes.get("operation_id", row.operation_id)
        target_name = (changes["name"].strip() if "name" in changes and changes["name"] else row.name)
        if not target_name:
            raise HTTPException(status_code=400, detail="Enter a name")
        other = await self._match(target_operation, target_name)
        if other is not None and other.id != row.id:
            raise HTTPException(status_code=409, detail="That name is already in this department")
        if target_operation != row.operation_id:
            await get_or_404(self.session, Operation, target_operation)
            await self._move(row, target_operation)
        row.name = target_name
        if "active" in changes and changes["active"] is not None:
            row.active = changes["active"]
        if "employment_type" in changes and changes["employment_type"]:
            row.employment_type = changes["employment_type"]
        for key in ("phone", "address", "emergency_contact_name", "emergency_contact_phone"):
            if key in changes:
                setattr(row, key, _blank(changes[key]))
        if wages:
            _apply_wages(row, changes.get("wage_kind"), changes.get("wage_amount") if "wage_amount" in changes else None, True)
        self.session.add(row)
        await commit_or_conflict(self.session)
        operation = await get_or_404(self.session, Operation, row.operation_id)
        return _worker_read(row, operation.name, reveal, wages)

    async def assigned(self, user_id: UUID) -> list[AssignedDepartment]:
        rows = (
            await self.session.execute(
                select(Operation)
                .join(UserOperation, UserOperation.operation_id == Operation.id)
                .where(UserOperation.user_id == user_id)
                .order_by(Operation.name)
            )
        ).scalars()
        found = list(rows)
        found.sort(key=lambda item: (_ROUTE.index(item.name.lower()) if item.name.lower() in _ROUTE else 99, item.name))
        return [AssignedDepartment(operation_id=row.id, name=row.name) for row in found]

    async def overview(
        self,
        date_from: date | None,
        date_to: date | None,
        *,
        reveal: bool,
        wages: bool = False,
    ) -> list[DepartmentRead]:
        start = date_from or (_today() - timedelta(days=6))
        end = date_to or _today()
        if start > end:
            raise HTTPException(status_code=400, detail="The start date is after the end date")
        operations = list(await self.session.scalars(select(Operation)))
        operations.sort(
            key=lambda item: (_ROUTE.index(item.name.lower()) if item.name.lower() in _ROUTE else 99, item.name)
        )
        from app.api.routes.machine.machine_model import Machine

        workers = list(await self.session.scalars(select(DepartmentWorker).order_by(DepartmentWorker.name)))
        machines = list(await self.session.scalars(select(Machine).order_by(Machine.name)))
        machine_names = {row.id: row.name for row in machines}
        active_rows = (
            await self.session.execute(
                select(ProductionJobStage, ProductionJob, Product.product_name, Product.quantity_per_bundle)
                .join(ProductionJob, ProductionJob.id == ProductionJobStage.job_id)
                .outerjoin(Product, Product.id == ProductionJob.product_id)
                .where(
                    ProductionJobStage.status == "active",
                    ProductionJob.status.in_(("in_progress", "pending")),
                )
            )
        ).all()
        job_ids = {job.id for _, job, _, _ in active_rows}
        inputs = await self._inputs(job_ids)
        sends_by_stage = await self._open_sends([stage.id for stage, _, _, _ in active_rows])
        by_operation: dict[UUID, DepartmentRead] = {}
        for operation in operations:
            people = [
                _worker_read(row, operation.name, reveal, wages)
                for row in workers
                if row.operation_id == operation.id and row.active
            ]
            by_operation[operation.id] = DepartmentRead(
                operation_id=operation.id,
                name=operation.name,
                workers=people,
                machines=[
                    DepartmentMachine(id=row.id, name=row.name, status=row.status, note=row.note)
                    for row in machines
                    if row.operation_id == operation.id
                ],
                active=[],
                recent=[],
                per_worker=[],
            )
        for stage, job, product_name, bundle in active_rows:
            bucket = by_operation.get(stage.operation_id)
            if bucket is None:
                continue
            good = Decimal(stage.good_quantity or 0)
            scrap = Decimal(stage.scrap_quantity or 0)
            sends = sends_by_stage.get(stage.id, [])
            outside_qty = sum((row.still_out for row in sends if row.still_out > 0), Decimal("0"))
            remaining = Decimal(job.quantity) - good - outside_qty
            if remaining < 0:
                remaining = Decimal("0")
            bucket.active.append(
                DepartmentActive(
                    job_id=job.id,
                    stage_id=stage.id,
                    product_name=product_name,
                    quantity=job.quantity,
                    good_quantity=good,
                    scrap_quantity=scrap,
                    remaining=remaining,
                    job_status=job.status,
                    problem_reason=stage.problem_reason,
                    problem_note=stage.problem_note,
                    problem_machine_name=machine_names.get(stage.problem_machine_id),
                    worker_name=stage.worker_name,
                    bundle_size=bundle,
                    started_at=stage.started_at,
                    due_at=job.due_at,
                    inputs=inputs.get(job.id, []),
                    allows_send_out=bool(stage.allows_send_out),
                    standard_scrap_percent=stage.standard_scrap_percent,
                    outside=[
                        OutsideOpen(supplier_name=row.supplier_name, quantity=row.still_out)
                        for row in sends
                        if row.still_out > 0
                    ],
                    sends=sends,
                )
            )
        entries = list(
            await self.session.scalars(
                select(FloorEntry)
                .where(FloorEntry.entry_date >= start, FloorEntry.entry_date <= end)
                .order_by(FloorEntry.entry_date.desc(), FloorEntry.created_at.desc())
            )
        )
        links: dict[UUID, list[FloorEntryWorker]] = {}
        if entries:
            for link in await self.session.scalars(
                select(FloorEntryWorker).where(
                    FloorEntryWorker.entry_id.in_([row.id for row in entries])  # type: ignore[attr-defined]
                )
            ):
                links.setdefault(link.entry_id, []).append(link)
        grouped: dict[UUID, list[FloorFact]] = {}
        for entry in entries:
            people = links.get(entry.id, [])
            fact = FloorFact(
                entry_id=str(entry.id),
                operation_id=str(entry.operation_id),
                entry_date=entry.entry_date,
                output_name=entry.output_name,
                output_unit=entry.output_unit,
                output_quantity=Decimal(entry.output_quantity),
                scrap_quantity=Decimal(entry.scrap_quantity or 0),
                scrap_unit=entry.scrap_unit,
                input_quantity=Decimal(entry.input_quantity) if entry.input_quantity is not None else None,
                input_unit=entry.input_unit,
                worker_ids=tuple(str(person.worker_id) for person in people),
            )
            grouped.setdefault(entry.operation_id, []).append(fact)
            bucket = by_operation.get(entry.operation_id)
            if bucket is None or len(bucket.recent) >= 10:
                continue
            labels = [person.worker_name for person in people] or ["Unassigned"]
            bucket.recent.append(
                DepartmentRecent(
                    worker_name=", ".join(labels),
                    product_name=entry.output_name,
                    quantity=entry.output_quantity,
                    scrap_quantity=entry.scrap_quantity,
                    notes=entry.notes,
                    unit=entry.output_unit,
                    completed_at=entry.created_at,
                    shared=len(people) > 1,
                )
            )
        worker_names = {str(row.id): row.name for row in workers}
        for operation_id, facts in grouped.items():
            bucket = by_operation.get(operation_id)
            if bucket is None:
                continue
            rolled = department_rollup(facts)
            bucket.output = _amounts(rolled.output)
            bucket.used = _amounts(rolled.used)
            bucket.scrap = _amounts(rolled.scrap)
            counts = []
            for worker_id, person in people_rollup(facts).items():
                counts.append(
                    WorkerCount(
                        worker_id=UUID(worker_id),
                        name=worker_names.get(worker_id, "Worker"),
                        stages=person.entries,
                        made=_amounts(person.output),
                    )
                )
            counts.sort(key=lambda item: (-item.stages, item.name))
            bucket.per_worker = counts
        return list(by_operation.values())

    async def _inputs(self, job_ids: set[UUID]) -> dict[UUID, list[DepartmentInput]]:
        inputs: dict[UUID, list[DepartmentInput]] = {}
        if not job_ids:
            return inputs
        material_rows = list(
            await self.session.scalars(
                select(ProductionJobInput).where(ProductionJobInput.job_id.in_(job_ids))  # type: ignore[attr-defined]
            )
        )
        product_ids = {row.product_id for row in material_rows if row.product_id}
        material_ids = {row.raw_material_id for row in material_rows if row.raw_material_id}
        product_names = (
            {
                row.id: row.product_name
                for row in await self.session.scalars(select(Product).where(Product.id.in_(product_ids)))  # type: ignore[attr-defined]
            }
            if product_ids
            else {}
        )
        materials = (
            {
                row.id: row
                for row in await self.session.scalars(select(RawMaterial).where(RawMaterial.id.in_(material_ids)))  # type: ignore[attr-defined]
            }
            if material_ids
            else {}
        )
        for row in material_rows:
            material = materials.get(row.raw_material_id) if row.raw_material_id else None
            name = product_names.get(row.product_id) if row.product_id else (material.name if material else None)
            inputs.setdefault(row.job_id, []).append(
                DepartmentInput(
                    input_id=row.id,
                    item_name=name or "Item",
                    planned_quantity=row.planned_quantity,
                    kind=material.kind if material else ("product" if row.product_id else None),
                    taken_quantity=row.taken_quantity,
                )
            )
        return inputs

    async def _open_sends(self, stage_ids: list[UUID]) -> dict[UUID, list[DeskSend]]:
        if not stage_ids:
            return {}
        from app.api.routes.production.production_model import StageSend
        from app.api.routes.supplier.supplier_model import Supplier

        rows = list(await self.session.scalars(select(StageSend).where(StageSend.stage_id.in_(stage_ids))))  # type: ignore[attr-defined]
        supplier_ids = {row.supplier_id for row in rows}
        names = (
            {
                row.id: row.supplier_company_name
                for row in await self.session.scalars(select(Supplier).where(Supplier.id.in_(supplier_ids)))  # type: ignore[attr-defined]
            }
            if supplier_ids
            else {}
        )
        grouped: dict[UUID, list[DeskSend]] = {}
        for row in rows:
            still = Decimal(row.quantity) - Decimal(row.good_quantity or 0) - Decimal(row.rejected_quantity or 0)
            grouped.setdefault(row.stage_id, []).append(
                DeskSend(
                    id=row.id,
                    supplier_id=row.supplier_id,
                    supplier_name=names.get(row.supplier_id, "Vendor"),
                    quantity=row.quantity,
                    sent_on=row.sent_on,
                    good_quantity=row.good_quantity,
                    rejected_quantity=row.rejected_quantity,
                    still_out=still,
                )
            )
        return grouped

    def _apply_profile(self, row: DepartmentWorker, data: WorkerWrite) -> None:
        row.phone = _blank(data.phone)
        row.employment_type = data.employment_type
        row.address = _blank(data.address)
        row.emergency_contact_name = _blank(data.emergency_contact_name)
        row.emergency_contact_phone = _blank(data.emergency_contact_phone)

    async def _ensure_history(self, row: DepartmentWorker) -> None:
        open_row = await self.session.scalar(
            select(WorkerDepartmentHistory).where(
                WorkerDepartmentHistory.worker_id == row.id,
                WorkerDepartmentHistory.ended_on.is_(None),
            )
        )
        if open_row is None:
            self.session.add(
                WorkerDepartmentHistory(worker_id=row.id, operation_id=row.operation_id, started_on=_today())
            )

    async def _move(self, row: DepartmentWorker, operation_id: UUID) -> None:
        today = _today()
        open_row = await self.session.scalar(
            select(WorkerDepartmentHistory).where(
                WorkerDepartmentHistory.worker_id == row.id,
                WorkerDepartmentHistory.ended_on.is_(None),
            )
        )
        if open_row is not None:
            open_row.ended_on = today
            self.session.add(open_row)
        self.session.add(WorkerDepartmentHistory(worker_id=row.id, operation_id=operation_id, started_on=today))
        row.operation_id = operation_id

    async def _match(self, operation_id: UUID, name: str) -> DepartmentWorker | None:
        return await self.session.scalar(
            select(DepartmentWorker).where(
                DepartmentWorker.operation_id == operation_id,
                func.lower(DepartmentWorker.name) == name.lower(),
            )
        )


def _apply_wages(row: DepartmentWorker, kind: str | None, amount: Decimal | None, wages: bool) -> None:
    if not wages:
        return
    if kind:
        row.wage_kind = kind
    if amount is not None:
        row.wage_amount = amount


def _worker_read(row: DepartmentWorker, operation_name: str, reveal: bool, wages: bool = False) -> WorkerRead:
    return WorkerRead(
        id=row.id,
        operation_id=row.operation_id,
        operation_name=operation_name,
        name=row.name,
        active=row.active,
        employment_type=row.employment_type or "permanent",
        phone=row.phone if reveal else None,
        address=row.address if reveal else None,
        emergency_contact_name=row.emergency_contact_name if reveal else None,
        emergency_contact_phone=row.emergency_contact_phone if reveal else None,
        wage_kind=row.wage_kind if wages else None,
        wage_amount=row.wage_amount if wages else None,
    )
