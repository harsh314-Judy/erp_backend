from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.department.department_model import DepartmentWorker, WorkerDepartmentHistory
from app.api.routes.floor.floor_aggregate import (
    FloorFact,
    daily_series,
    department_average,
    department_rollup,
    item_breakdown,
    people_rollup,
    worker_rollup,
)
from app.api.routes.floor.floor_model import FloorEntry, FloorEntryWorker
from app.api.routes.floor.floor_schemas import (
    DailyPoint,
    DepartmentSummary,
    EntryWorker,
    FeedItem,
    FloorEntryRead,
    FloorEntryWrite,
    FloorSummary,
    HistorySpan,
    ItemTotal,
    PersonTotal,
    ScrapRate,
    UnitTotal,
    WorkerNow,
    WorkerTimeline,
)
from app.api.routes.operation.operation_model import Operation
from app.api.routes.product.product_model import MeasurementUnit, Product
from app.api.routes.production.production_model import ProductionJob
from app.api.routes.user.user_model import User
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.db.repository import commit_or_conflict, get_or_404, to_page

_KOLKATA = ZoneInfo("Asia/Kolkata")
_ROUTE = ["cutting", "shaping", "assembly", "polishing", "coloring", "packaging"]


def today_ist() -> date:
    return datetime.now(_KOLKATA).date()


def _span(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    start = date_from or today_ist()
    end = date_to or start
    if start > end:
        raise HTTPException(status_code=400, detail="The start date is after the end date")
    return start, end


def _amounts(bucket: dict[str, Decimal]) -> list[UnitTotal]:
    return [
        UnitTotal(unit=unit, quantity=amount)
        for unit, amount in sorted(bucket.items())
        if amount != 0
    ]


def _rates(bucket: dict[str, Decimal | None], units: dict[str, Decimal]) -> list[ScrapRate]:
    return [ScrapRate(unit=unit, percent=bucket.get(unit)) for unit in sorted(units)]


def _as_fact(entry: FloorEntry, worker_ids: tuple[str, ...]) -> FloorFact:
    return FloorFact(
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
        worker_ids=worker_ids,
    )


class FloorService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def summary(self, date_from: date | None, date_to: date | None) -> FloorSummary:
        start, end = _span(date_from, date_to)
        operations = await self._operations()
        entries = await self._entries_between(start, end)
        workers = await self._links([row.id for row in entries])
        open_jobs = dict(
            (
                await self.session.execute(
                    select(ProductionJob.current_operation_id, func.count())
                    .where(ProductionJob.status == "in_progress")
                    .group_by(ProductionJob.current_operation_id)
                )
            ).all()
        )
        names = {row.id: row.name for row in await self.session.scalars(select(DepartmentWorker))}
        by_operation: dict[UUID, list[FloorEntry]] = {row.id: [] for row in operations}
        for entry in entries:
            by_operation.setdefault(entry.operation_id, []).append(entry)
        departments: list[DepartmentSummary] = []
        for operation in operations:
            rows = by_operation.get(operation.id, [])
            facts = [self._fact(row, workers) for row in rows]
            rolled = department_rollup(facts)
            people = []
            for worker_id, person in people_rollup(facts).items():
                people.append(
                    PersonTotal(
                        worker_id=UUID(worker_id),
                        name=names.get(UUID(worker_id), "Worker"),
                        made=_amounts(person.output),
                    )
                )
            people.sort(key=lambda item: item.name.lower())
            departments.append(
                DepartmentSummary(
                    operation_id=operation.id,
                    name=operation.name,
                    entries=rolled.entries,
                    workers=len(people),
                    open_jobs=int(open_jobs.get(operation.id, 0)),
                    output=_amounts(rolled.output),
                    used=_amounts(rolled.used),
                    scrap=_amounts(rolled.scrap),
                    scrap_pct=_rates(rolled.scrap_pct, rolled.output),
                    people=people,
                )
            )
        return FloorSummary(date_from=start, date_to=end, departments=departments)

    async def list_entries(
        self,
        pagination: PaginationParams,
        *,
        operation_id: UUID | None,
        worker_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
    ) -> PaginatedResponse[FloorEntryRead]:
        start, end = _span(date_from, date_to)
        query = select(FloorEntry).where(FloorEntry.entry_date >= start, FloorEntry.entry_date <= end)
        if operation_id is not None:
            query = query.where(FloorEntry.operation_id == operation_id)
        if worker_id is not None:
            query = query.where(
                FloorEntry.id.in_(  # type: ignore[attr-defined]
                    select(FloorEntryWorker.entry_id).where(FloorEntryWorker.worker_id == worker_id)
                )
            )
        query = query.order_by(FloorEntry.entry_date.desc(), FloorEntry.created_at.desc())
        rows = list(await self.session.scalars(query))
        page = rows[pagination.offset : pagination.offset + pagination.page_size]
        return to_page(await self._reads(page), len(rows), pagination)

    async def create_entry(self, data: FloorEntryWrite, actor: User) -> FloorEntryRead:
        workers = await self._require_workers(data.worker_ids)
        await get_or_404(self.session, Operation, data.operation_id)
        entry = FloorEntry(
            entry_date=data.entry_date,
            operation_id=data.operation_id,
            created_by_user_id=actor.id,
            **self._payload(data),
        )
        self.session.add(entry)
        await self.session.flush()
        self._attach(entry, workers)
        await commit_or_conflict(self.session)
        await self.session.refresh(entry)
        return (await self._reads([entry]))[0]

    async def update_entry(self, entry_id: UUID, data: FloorEntryWrite, actor: User, *, can_edit_others: bool) -> FloorEntryRead:
        entry = await get_or_404(self.session, FloorEntry, entry_id)
        self._assert_editable(entry, actor, can_edit_others)
        workers = await self._require_workers(data.worker_ids)
        await get_or_404(self.session, Operation, data.operation_id)
        for key, value in self._payload(data).items():
            setattr(entry, key, value)
        entry.entry_date = data.entry_date
        entry.operation_id = data.operation_id
        self.session.add(entry)
        await self.session.execute(delete(FloorEntryWorker).where(FloorEntryWorker.entry_id == entry.id))
        self._attach(entry, workers)
        await commit_or_conflict(self.session)
        return (await self._reads([entry]))[0]

    async def delete_entry(self, entry_id: UUID, actor: User, *, can_edit_others: bool) -> None:
        entry = await get_or_404(self.session, FloorEntry, entry_id)
        self._assert_editable(entry, actor, can_edit_others)
        await self.session.execute(delete(FloorEntryWorker).where(FloorEntryWorker.entry_id == entry.id))
        await self.session.delete(entry)
        await commit_or_conflict(self.session)

    async def record_stage(
        self,
        *,
        stage_id: UUID,
        job_id: UUID,
        operation_id: UUID,
        product_id: UUID | None,
        output_name: str,
        output_quantity: Decimal,
        output_unit: str,
        scrap_quantity: Decimal,
        workers: list[DepartmentWorker],
        actor: User,
    ) -> None:
        existing = await self.session.scalar(select(FloorEntry).where(FloorEntry.stage_id == stage_id))
        if existing is not None:
            await self.session.execute(delete(FloorEntryWorker).where(FloorEntryWorker.entry_id == existing.id))
            await self.session.delete(existing)
            await self.session.flush()
        entry = FloorEntry(
            entry_date=today_ist(),
            operation_id=operation_id,
            output_product_id=product_id,
            output_name=output_name[:255],
            output_quantity=output_quantity,
            output_unit=(output_unit or "pcs")[:16],
            scrap_quantity=scrap_quantity,
            scrap_unit=(output_unit or "pcs")[:16] if scrap_quantity else None,
            job_id=job_id,
            stage_id=stage_id,
            created_by_user_id=actor.id,
        )
        self.session.add(entry)
        await self.session.flush()
        self._attach(entry, workers)

    async def drop_stage(self, stage_id: UUID) -> None:
        entry = await self.session.scalar(select(FloorEntry).where(FloorEntry.stage_id == stage_id))
        if entry is None:
            return
        await self.session.execute(delete(FloorEntryWorker).where(FloorEntryWorker.entry_id == entry.id))
        await self.session.delete(entry)

    async def timeline(
        self,
        worker_id: UUID,
        date_from: date | None,
        date_to: date | None,
        *,
        reveal_contact: bool,
    ) -> WorkerTimeline:
        start, end = _span(date_from, date_to)
        worker = await get_or_404(self.session, DepartmentWorker, worker_id)
        operation = await get_or_404(self.session, Operation, worker.operation_id)
        history_rows = list(
            await self.session.scalars(
                select(WorkerDepartmentHistory)
                .where(WorkerDepartmentHistory.worker_id == worker.id)
                .order_by(WorkerDepartmentHistory.started_on)
            )
        )
        operations = {row.id: row.name for row in await self._operations()}
        entry_ids = list(
            await self.session.scalars(
                select(FloorEntryWorker.entry_id).where(FloorEntryWorker.worker_id == worker.id)
            )
        )
        own_entries = []
        if entry_ids:
            own_entries = list(
                await self.session.scalars(
                    select(FloorEntry)
                    .where(
                        FloorEntry.id.in_(entry_ids),  # type: ignore[attr-defined]
                        FloorEntry.entry_date >= start,
                        FloorEntry.entry_date <= end,
                    )
                    .order_by(FloorEntry.entry_date.desc(), FloorEntry.created_at.desc())
                )
            )
        dept_entries = list(
            await self.session.scalars(
                select(FloorEntry).where(
                    FloorEntry.operation_id == worker.operation_id,
                    FloorEntry.entry_date >= start,
                    FloorEntry.entry_date <= end,
                )
            )
        )
        needed = {row.id for row in own_entries} | {row.id for row in dept_entries}
        links = await self._links(list(needed))
        own_facts = [self._fact(row, links) for row in own_entries]
        dept_facts = [self._fact(row, links) for row in dept_entries]
        rolled = worker_rollup(own_facts, str(worker.id))
        today = today_ist()
        today_entries = 0
        last_at = None
        if entry_ids:
            today_entries = int(
                await self.session.scalar(
                    select(func.count())
                    .select_from(FloorEntry)
                    .where(FloorEntry.id.in_(entry_ids), FloorEntry.entry_date == today)  # type: ignore[attr-defined]
                )
                or 0
            )
            last_row = await self.session.scalar(
                select(FloorEntry)
                .where(FloorEntry.id.in_(entry_ids))  # type: ignore[attr-defined]
                .order_by(FloorEntry.created_at.desc())
            )
            last_at = last_row.created_at if last_row is not None else None
        open_jobs = int(
            await self.session.scalar(
                select(func.count())
                .select_from(ProductionJob)
                .where(
                    ProductionJob.status == "in_progress",
                    ProductionJob.current_operation_id == worker.operation_id,
                )
            )
            or 0
        )
        averages = {
            unit: (rolled.output[unit] / Decimal(len(rolled.active_days))).quantize(Decimal("0.001"))
            for unit in rolled.output
            if rolled.active_days
        }
        dept_avg = department_average(dept_facts, str(worker.operation_id))
        return WorkerTimeline(
            worker_id=worker.id,
            name=worker.name,
            active=worker.active,
            employment_type=worker.employment_type,
            phone=worker.phone if reveal_contact else None,
            address=worker.address if reveal_contact else None,
            emergency_contact_name=worker.emergency_contact_name if reveal_contact else None,
            emergency_contact_phone=worker.emergency_contact_phone if reveal_contact else None,
            operation_id=worker.operation_id,
            operation_name=operation.name,
            date_from=start,
            date_to=end,
            history=[
                HistorySpan(
                    operation_id=row.operation_id,
                    operation_name=operations.get(row.operation_id, "Department"),
                    started_on=row.started_on,
                    ended_on=row.ended_on,
                )
                for row in history_rows
            ],
            now=WorkerNow(
                department=operation.name,
                last_entry_at=last_at,
                today_entries=today_entries,
                open_jobs_in_department=open_jobs,
            ),
            output=_amounts(rolled.output),
            used=_amounts(rolled.used),
            scrap=_amounts(rolled.scrap),
            scrap_pct=_rates(rolled.scrap_pct, rolled.output),
            active_days=len(rolled.active_days),
            avg_per_active_day=_amounts(averages),
            shared_entries=rolled.shared_entries,
            department_avg_per_worker_day=_amounts(dept_avg),
            daily=[DailyPoint(**row) for row in daily_series(own_facts, str(worker.id))],
            items=[ItemTotal(**row) for row in item_breakdown(own_facts, str(worker.id))],
            feed=self._feed(own_entries, links, history_rows, operations, str(worker.id), start, end),
        )

    def _feed(
        self,
        entries: list[FloorEntry],
        links: dict[UUID, list[FloorEntryWorker]],
        history: list[WorkerDepartmentHistory],
        operations: dict[UUID, str],
        worker_id: str,
        start: date,
        end: date,
    ) -> list[FeedItem]:
        items: list[FeedItem] = []
        for entry in entries:
            people = links.get(entry.id, [])
            others = [row.worker_name for row in people if str(row.worker_id) != worker_id]
            made = f"{_trim(entry.output_quantity)} {entry.output_unit} {entry.output_name}"
            extra = ""
            if entry.scrap_quantity:
                extra = f" · scrap {_trim(entry.scrap_quantity)} {entry.scrap_unit or entry.output_unit}"
            items.append(
                FeedItem(
                    at=_stamp(entry.entry_date, entry.created_at),
                    kind="entry",
                    title=made + extra,
                    detail=entry.notes or ("From a production job" if entry.stage_id else "Logged on the floor"),
                    shared_with=others,
                )
            )
        for row in history:
            if row.started_on < start or row.started_on > end:
                continue
            name = operations.get(row.operation_id, "a department")
            items.append(
                FeedItem(
                    at=datetime.combine(row.started_on, time(0, 0), tzinfo=_KOLKATA),
                    kind="move",
                    title=f"Moved to {name}" if row.ended_on is not None or len(history) > 1 else f"Joined {name}",
                    detail="Department change",
                    shared_with=[],
                )
            )
        items.sort(key=lambda item: item.at, reverse=True)
        return items

    async def _operations(self) -> list[Operation]:
        rows = list(await self.session.scalars(select(Operation)))
        rows.sort(key=lambda item: (_ROUTE.index(item.name.lower()) if item.name.lower() in _ROUTE else 99, item.name))
        return rows

    async def _entries_between(self, start: date, end: date) -> list[FloorEntry]:
        return list(
            await self.session.scalars(
                select(FloorEntry).where(FloorEntry.entry_date >= start, FloorEntry.entry_date <= end)
            )
        )

    async def _links(self, entry_ids: list[UUID]) -> dict[UUID, list[FloorEntryWorker]]:
        grouped: dict[UUID, list[FloorEntryWorker]] = {}
        if not entry_ids:
            return grouped
        rows = await self.session.scalars(
            select(FloorEntryWorker)
            .where(FloorEntryWorker.entry_id.in_(entry_ids))  # type: ignore[attr-defined]
            .order_by(FloorEntryWorker.worker_name)
        )
        for row in rows:
            grouped.setdefault(row.entry_id, []).append(row)
        return grouped

    def _fact(self, entry: FloorEntry, links: dict[UUID, list[FloorEntryWorker]]) -> FloorFact:
        return _as_fact(entry, tuple(str(row.worker_id) for row in links.get(entry.id, [])))

    async def _reads(self, entries: list[FloorEntry]) -> list[FloorEntryRead]:
        if not entries:
            return []
        links = await self._links([row.id for row in entries])
        operations = {row.id: row.name for row in await self._operations()}
        user_ids = {row.created_by_user_id for row in entries if row.created_by_user_id}
        names: dict[UUID, str] = {}
        if user_ids:
            for person in await self.session.scalars(select(User).where(User.id.in_(user_ids))):  # type: ignore[attr-defined]
                names[person.id] = " ".join(part for part in (person.first_name, person.last_name) if part).strip()
        return [
            FloorEntryRead(
                id=entry.id,
                entry_date=entry.entry_date,
                operation_id=entry.operation_id,
                operation_name=operations.get(entry.operation_id, "Department"),
                workers=[EntryWorker(id=row.worker_id, name=row.worker_name) for row in links.get(entry.id, [])],
                output_name=entry.output_name,
                output_quantity=entry.output_quantity,
                output_unit=entry.output_unit,
                output_product_id=entry.output_product_id,
                input_name=entry.input_name,
                input_quantity=entry.input_quantity,
                input_unit=entry.input_unit,
                input_product_id=entry.input_product_id,
                input_raw_material_id=entry.input_raw_material_id,
                scrap_quantity=entry.scrap_quantity,
                scrap_unit=entry.scrap_unit,
                notes=entry.notes,
                from_job=entry.stage_id is not None,
                job_id=entry.job_id,
                created_by_name=names.get(entry.created_by_user_id) if entry.created_by_user_id else None,
                created_at=entry.created_at,
            )
            for entry in entries
        ]

    async def _require_workers(self, worker_ids: list[UUID]) -> list[DepartmentWorker]:
        found: list[DepartmentWorker] = []
        seen: set[UUID] = set()
        for worker_id in worker_ids:
            if worker_id in seen:
                continue
            seen.add(worker_id)
            worker = await self.session.get(DepartmentWorker, worker_id)
            if worker is None or not worker.active:
                raise HTTPException(status_code=400, detail="Choose people who are currently on the roster")
            found.append(worker)
        if not found:
            raise HTTPException(status_code=400, detail="Choose at least one person")
        return found

    def _attach(self, entry: FloorEntry, workers: list[DepartmentWorker]) -> None:
        for worker in workers:
            self.session.add(
                FloorEntryWorker(entry_id=entry.id, worker_id=worker.id, worker_name=worker.name[:120])
            )

    def _payload(self, data: FloorEntryWrite) -> dict:
        scrap_unit = data.scrap_unit or (data.output_unit if data.scrap_quantity else None)
        input_name = (data.input_name or "").strip() or None
        return {
            "output_product_id": data.output_product_id,
            "output_name": data.output_name.strip()[:255],
            "output_quantity": data.output_quantity,
            "output_unit": data.output_unit.strip()[:16],
            "input_product_id": data.input_product_id,
            "input_raw_material_id": data.input_raw_material_id,
            "input_name": input_name[:255] if input_name else None,
            "input_quantity": data.input_quantity if input_name else None,
            "input_unit": (data.input_unit or "").strip()[:16] or None if input_name else None,
            "scrap_quantity": data.scrap_quantity,
            "scrap_unit": (scrap_unit or "").strip()[:16] or None,
            "notes": (data.notes or "").strip() or None,
        }

    def _assert_editable(self, entry: FloorEntry, actor: User, can_edit_others: bool) -> None:
        if entry.stage_id is not None:
            raise HTTPException(status_code=409, detail="This line came from a job. Revert the stage instead")
        if entry.created_by_user_id != actor.id and not can_edit_others:
            raise HTTPException(status_code=403, detail="You can only change lines you logged")


def _trim(value: Decimal) -> str:
    return format(Decimal(value).normalize(), "f")


def _stamp(day: date, created_at: datetime) -> datetime:
    clock = created_at.astimezone(_KOLKATA).timetz().replace(tzinfo=None)
    return datetime.combine(day, clock, tzinfo=_KOLKATA).astimezone(timezone.utc)
