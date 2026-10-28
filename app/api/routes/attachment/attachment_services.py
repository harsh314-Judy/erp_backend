from uuid import uuid4

from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile

from app.api.routes.attachment.attachment_model import Attachment
from app.api.routes.user.user_model import User
from app.config import db_settings, media_settings
from app.db.repository import commit_or_conflict


class AttachmentService:
    def __init__(self, client: BaseClient) -> None:
        self.client = client

    async def upload(self, session, file: UploadFile, actor: User) -> Attachment:
        content_type = file.content_type or "application/octet-stream"
        allowed = media_settings.allowed_image_types | media_settings.allowed_document_types
        if content_type not in allowed:
            raise HTTPException(status_code=400, detail="This file type is not allowed")
        payload = await file.read()
        limit = (
            media_settings.MEDIA_MAX_IMAGE_BYTES
            if content_type in media_settings.allowed_image_types
            else media_settings.MEDIA_MAX_DOCUMENT_BYTES
        )
        if len(payload) > limit:
            raise HTTPException(status_code=400, detail="File is too large")
        key = f"attachments/{uuid4()}-{file.filename or 'file'}"
        await self.client.put_object(
            Bucket=db_settings.GARAGE_BUCKET_NAME,
            Key=key,
            Body=payload,
            ContentType=content_type,
        )
        row = Attachment(
            object_key=key,
            filename=file.filename or "file",
            content_type=content_type,
            size_bytes=len(payload),
            uploaded_by_user_id=actor.id,
        )
        session.add(row)
        await commit_or_conflict(session)
        await session.refresh(row)
        return row

    async def store_bytes(
        self,
        session,
        *,
        filename: str,
        content_type: str,
        payload: bytes,
        actor: User,
        key_prefix: str = "invoices",
    ) -> Attachment:
        key = f"{key_prefix}/{uuid4()}-{filename}"
        try:
            await self.client.put_object(
                Bucket=db_settings.GARAGE_BUCKET_NAME,
                Key=key,
                Body=payload,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise HTTPException(status_code=502, detail="Could not store the file in Garage") from exc
        row = Attachment(
            object_key=key,
            filename=filename,
            content_type=content_type,
            size_bytes=len(payload),
            uploaded_by_user_id=actor.id,
        )
        session.add(row)
        await session.flush()
        return row

    async def read_bytes(self, key: str) -> bytes:
        try:
            response = await self.client.get_object(Bucket=db_settings.GARAGE_BUCKET_NAME, Key=key)
            return await response["Body"].read()
        except (BotoCoreError, ClientError) as exc:
            raise HTTPException(status_code=502, detail="Could not read the file from Garage") from exc
