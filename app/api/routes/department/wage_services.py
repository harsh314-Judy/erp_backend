from calendar import monthrange
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.department.department_model import DepartmentWorker, FloorDay, WorkerMonthPay
from app.api.routes.department.wage_schemas import (
    AdvanceWrite,
    DayMark,
    WageDay,
    WageMonth,
    WagePerson,
)
from app.api.routes.operation.operation_model import Operation
from app.db.repository import commit_or_conflict, get_or_404


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _owed(kind: str, amount: Decimal, active: bool, present: int, half: int) -> Decimal:
    rate = money(amount)
    if kind == "monthly":
        return rate if active else Decimal("0.00")
    return money((Decimal(present) + (Decimal(half) * Decimal("0.5"))) * rate)


class WageService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def month(self, year: int, month: int) -> WageMonth:
        if month < 1 or month > 12 or year < 2000 or year > 2100:
            raise HTTPException(status_code=400, detail="Choose a real month")
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        workers = (
            await self.session.execute(
                select(DepartmentWorker, Operation.name)
                .join(Operation, Operation.id == DepartmentWorker.operation_id)
                .order_by(Operation.name, DepartmentWorker.name)
            )
        ).all()
        marks = list(
            await self.session.scalars(
                select(FloorDay).where(FloorDay.work_date >= start, FloorDay.work_date <= end)
            )
        )
        advances = list(
            await self.session.scalars(
                select(WorkerMonthPay).where(WorkerMonthPay.year == year, WorkerMonthPay.month == month)
            )
        )
        by_worker: dict[UUID, list[FloorDay]] = {}
        for row in marks:
            by_worker.setdefault(row.worker_id, []).append(row)
        given = {row.worker_id: row for row in advances}
        people: list[WagePerson] = []
        total = Decimal("0.00")
        for worker, operation_name in workers:
            days = sorted(by_worker.get(worker.id, []), key=lambda item: item.work_date)
            advance = given.get(worker.id)
            already = money(advance.already_given) if advance is not None else Decimal("0.00")
            if not worker.active and not days and already == 0:
                continue
            present = sum(1 for row in days if row.status == "present")
            half = sum(1 for row in days if row.status == "half")
            gross = _owed(worker.wage_kind or "daily", worker.wage_amount, worker.active, present, half)
            owed = money(gross - already)
            total += owed
            people.append(
                WagePerson(
                    worker_id=worker.id,
                    name=worker.name,
                    operation_name=operation_name,
                    active=worker.active,
                    wage_kind=worker.wage_kind or "daily",
                    wage_amount=money(worker.wage_amount),
                    present_days=present,
                    half_days=half,
                    absent_dates=[row.work_date for row in days if row.status == "absent"],
                    days=[WageDay(work_date=row.work_date, status=row.status) for row in days],
                    already_given=already,
                    owed=owed,
                )
            )
        return WageMonth(year=year, month=month, people=people, total_owed=money(total))

    async def mark_day(self, data: DayMark) -> WageMonth:
        await get_or_404(self.session, DepartmentWorker, data.worker_id)
        existing = await self.session.scalar(
            select(FloorDay).where(
                FloorDay.worker_id == data.worker_id,
                FloorDay.work_date == data.work_date,
            )
        )
        if data.status is None:
            if existing is not None:
                await self.session.delete(existing)
        elif existing is None:
            self.session.add(
                FloorDay(worker_id=data.worker_id, work_date=data.work_date, status=data.status)
            )
        else:
            existing.status = data.status
            self.session.add(existing)
        await commit_or_conflict(self.session)
        return await self.month(data.work_date.year, data.work_date.month)

    async def set_advance(self, data: AdvanceWrite) -> WageMonth:
        await get_or_404(self.session, DepartmentWorker, data.worker_id)
        existing = await self.session.scalar(
            select(WorkerMonthPay).where(
                WorkerMonthPay.worker_id == data.worker_id,
                WorkerMonthPay.year == data.year,
                WorkerMonthPay.month == data.month,
            )
        )
        amount = money(data.already_given)
        if existing is None:
            self.session.add(
                WorkerMonthPay(
                    worker_id=data.worker_id,
                    year=data.year,
                    month=data.month,
                    already_given=amount,
                )
            )
        else:
            existing.already_given = amount
            self.session.add(existing)
        await commit_or_conflict(self.session)
        return await self.month(data.year, data.month)
