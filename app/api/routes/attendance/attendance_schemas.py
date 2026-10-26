from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AttendanceRead(BaseModel):
    id: UUID
    person: str
    role_name: str
    signed_in_at: datetime
    signed_out_at: datetime | None
