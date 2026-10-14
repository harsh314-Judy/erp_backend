from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    body: str
    kind: str
    link: str | None
    read_at: datetime | None
    created_at: datetime
