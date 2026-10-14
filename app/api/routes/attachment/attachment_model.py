from uuid import UUID

from sqlmodel import Field

from app.db.base import Entity


class Attachment(Entity, table=True):
    __tablename__ = "attachments"

    object_key: str = Field(max_length=255, unique=True, nullable=False)
    filename: str = Field(max_length=255, nullable=False)
    content_type: str = Field(max_length=120, nullable=False)
    size_bytes: int = Field(nullable=False)
    uploaded_by_user_id: UUID | None = Field(
        default=None, foreign_key="users.id", nullable=True, index=True, ondelete="SET NULL"
    )
