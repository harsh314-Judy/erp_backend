from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    occurred_at: datetime
    kind: str
    summary: str
    ref_type: str
    ref_id: UUID | None
    link: str | None
