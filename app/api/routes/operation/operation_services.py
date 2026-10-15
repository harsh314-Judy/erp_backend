from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.operation.operation_model import Operation, UserOperation
from app.api.routes.operation.operation_schemas import (
    OperationCreate,
    OperationRead,
    OperationUpdate,
    UserOperationCreate,
    UserOperationRead,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.db.repository import (
    create_model,
    delete_model,
    get_or_404,
    list_models,
    to_page,
    update_model,
)

PROTECTED_OPERATIONS = {
    "cutting",
    "shaping",
    "assembly",
    "polishing",
    "coloring",
    "packaging",
}


class OperationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_operations(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[OperationRead]:
        rows, total = await list_models(self.session, Operation, pagination)
        return to_page([OperationRead.model_validate(row) for row in rows], total, pagination)

    async def create_operation(self, data: OperationCreate) -> OperationRead:
        row = await create_model(self.session, Operation, data)
        return OperationRead.model_validate(row)

    async def update_operation(
        self, operation_id: UUID, data: OperationUpdate
    ) -> OperationRead:
        current = await get_or_404(self.session, Operation, operation_id)
        incoming = data.name.strip().lower() if data.name else None
        if current.name.lower() in PROTECTED_OPERATIONS and incoming not in (
            None,
            current.name.lower(),
        ):
            raise HTTPException(status_code=409, detail="This operation name is part of the plant route")
        row = await update_model(self.session, Operation, operation_id, data)
        return OperationRead.model_validate(row)

    async def delete_operation(self, operation_id: UUID) -> None:
        current = await get_or_404(self.session, Operation, operation_id)
        if current.name.lower() in PROTECTED_OPERATIONS:
            raise HTTPException(status_code=409, detail="This operation is part of the plant route")
        await delete_model(self.session, Operation, operation_id)

    async def list_assignments(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[UserOperationRead]:
        rows, total = await list_models(self.session, UserOperation, pagination)
        return to_page(
            [UserOperationRead.model_validate(row) for row in rows], total, pagination
        )

    async def create_assignment(self, data: UserOperationCreate) -> UserOperationRead:
        row = await create_model(self.session, UserOperation, data)
        return UserOperationRead.model_validate(row)

    async def delete_assignment(self, assignment_id: UUID) -> None:
        await delete_model(self.session, UserOperation, assignment_id)
