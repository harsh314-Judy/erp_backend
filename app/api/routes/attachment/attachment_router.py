from fastapi import APIRouter, File, UploadFile, status

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import AttachmentServiceDep, CurrentUserDep
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
