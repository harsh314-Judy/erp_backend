from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import AttachmentServiceDep, CurrentUserDep
from app.api.routes.attachment.attachment_model import Attachment
from app.api.routes.attachment.attachment_schemas import AttachmentRead

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.post("", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    session: PGSessionDep,
    user: CurrentUserDep,
    service: AttachmentServiceDep,
    file: UploadFile = File(...),
) -> AttachmentRead:
    row = await service.upload(session, file, user)
    return AttachmentRead.model_validate(row)


@router.get("/{attachment_id}/file")
async def read_attachment(
    attachment_id: UUID,
    session: PGSessionDep,
    user: CurrentUserDep,
    service: AttachmentServiceDep,
) -> Response:
    row = await session.get(Attachment, attachment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")
    payload = await service.read_bytes(row.object_key)
    safe_name = row.filename.replace('"', "")
    return Response(
        content=payload,
        media_type=row.content_type,
        headers={
            "Cache-Control": "private, max-age=86400",
            "Content-Disposition": f'inline; filename="{safe_name}"',
        },
    )
