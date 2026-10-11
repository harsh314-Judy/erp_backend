from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.customer.customer_model import Customer
from app.api.routes.customer.customer_schemas import (
    CustomerCreate,
    CustomerRead,
    CustomerUpdate,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.db.repository import (
    delete_model,
    get_or_404,
    list_models,
    to_page,
    update_model,
)
from app.db.repository import commit_or_conflict


class CustomerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_customers(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[CustomerRead]:
        rows, total = await list_models(self.session, Customer, pagination)
        return to_page(
            [CustomerRead.model_validate(row) for row in rows], total, pagination
        )

    async def get_customer(self, customer_id: UUID) -> CustomerRead:
        return CustomerRead.model_validate(
            await get_or_404(self.session, Customer, customer_id)
        )

    async def create_customer(self, data: CustomerCreate) -> CustomerRead:
        payload = data.model_dump()
        payload["email"] = data.email.strip().lower()
        row = Customer.model_validate(payload)
        self.session.add(row)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return CustomerRead.model_validate(row)

    async def update_customer(
        self, customer_id: UUID, data: CustomerUpdate
    ) -> CustomerRead:
        row = await update_model(self.session, Customer, customer_id, data)
        return CustomerRead.model_validate(row)

    async def delete_customer(self, customer_id: UUID) -> None:
        await delete_model(self.session, Customer, customer_id)
