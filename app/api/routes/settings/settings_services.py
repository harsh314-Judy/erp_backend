from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.settings.settings_model import CompanySettings
from app.api.routes.settings.settings_schemas import CompanyRead, CompanyUpdate
from app.db.repository import commit_or_conflict


class SettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_company(self) -> CompanyRead:
        row = await self._row()
        return CompanyRead.model_validate(row)

    async def update_company(self, data: CompanyUpdate) -> CompanyRead:
        row = await self._row()
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        self.session.add(row)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return CompanyRead.model_validate(row)

    async def _row(self) -> CompanySettings:
        row = await self.session.scalar(select(CompanySettings))
        if row is None:
            row = CompanySettings(company_name="Sai Daya Steel")
            self.session.add(row)
            await commit_or_conflict(self.session)
            await self.session.refresh(row)
        return row
