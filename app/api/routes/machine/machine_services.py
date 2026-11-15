from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.machine.machine_model import Machine
from app.api.routes.machine.machine_schemas import MachineCreate, MachineRead, MachineUpdate
from app.api.routes.operation.operation_model import Operation
from app.db.repository import commit_or_conflict, get_or_404


class MachineService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_machines(self, operation_id: UUID | None) -> list[MachineRead]:
        statement = select(Machine, Operation.name).join(Operation, Operation.id == Machine.operation_id)
        if operation_id is not None:
            statement = statement.where(Machine.operation_id == operation_id)
        rows = (await self.session.execute(statement.order_by(Operation.name, Machine.name))).all()
        return [
            MachineRead.model_validate(machine).model_copy(update={"operation_name": operation_name})
            for machine, operation_name in rows
        ]

    async def create_machine(self, data: MachineCreate) -> MachineRead:
        await get_or_404(self.session, Operation, data.operation_id)
        row = Machine(
            name=data.name.strip(),
            operation_id=data.operation_id,
            status="up",
            note=(data.note or "").strip() or None,
        )
        self.session.add(row)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        operation = await self.session.get(Operation, row.operation_id)
        return MachineRead.model_validate(row).model_copy(
            update={"operation_name": operation.name if operation else ""}
        )

    async def update_machine(self, machine_id: UUID, data: MachineUpdate) -> MachineRead:
        row = await get_or_404(self.session, Machine, machine_id)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"] is not None:
            row.name = changes["name"].strip()
        if "status" in changes and changes["status"] is not None:
            row.status = changes["status"]
        if "note" in changes:
            row.note = (changes["note"] or "").strip() or None
        if not changes:
            raise HTTPException(status_code=400, detail="Nothing changed")
        self.session.add(row)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        operation = await self.session.get(Operation, row.operation_id)
        return MachineRead.model_validate(row).model_copy(
            update={"operation_name": operation.name if operation else ""}
        )
