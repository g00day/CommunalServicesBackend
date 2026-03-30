from fastapi import APIRouter, Depends, File as FastAPIFile, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import (
    ChatParticipantCreate,
    ChatParticipantOut,
    MessageFileOut,
    MessageOut,
    TicketFileOut,
)
from app.services.ticket_chat import (
    add_chat_participant_service,
    create_message_service,
    get_chat_participants_service,
    get_message_files_service,
    get_ticket_files_service,
    get_ticket_messages_service,
)


router = APIRouter(prefix="/tickets", tags=["ticket-messages"])


@router.get("/{ticket_id}/messages", response_model=list[MessageOut])
async def get_ticket_messages(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_ticket_messages_service(db, ticket_id, current_user)


@router.post("/{ticket_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def create_message(
    ticket_id: int,
    text: str | None = Form(default=None),
    files: list[UploadFile] = FastAPIFile(default=[]),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_message_service(db, ticket_id, text, current_user, files)


@router.get("/{ticket_id}/participants", response_model=list[ChatParticipantOut])
async def get_chat_participants(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_chat_participants_service(db, ticket_id, current_user)


@router.post("/{ticket_id}/participants", response_model=ChatParticipantOut, status_code=status.HTTP_201_CREATED)
async def add_chat_participant(
    ticket_id: int,
    payload: ChatParticipantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await add_chat_participant_service(
        db,
        ticket_id,
        payload.user_id,
        payload.role_in_chat,
        current_user,
    )


@router.get("/{ticket_id}/files", response_model=list[TicketFileOut])
async def get_ticket_files(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_ticket_files_service(db, ticket_id, current_user)


@router.get("/{ticket_id}/messages/{message_id}/files", response_model=list[MessageFileOut])
async def get_message_files(
    ticket_id: int,
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_message_files_service(db, ticket_id, message_id, current_user)

