import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.core.errors import NotFoundError
from app.models.agent import AgentConversation, AgentMessage
from app.models.user import User
from app.schemas.agent import (
    ConversationCreate,
    ConversationDetail,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(prefix="/agent", tags=["agent"])


def _get_own_conversation(
    db: DbSession, conversation_id: uuid.UUID, user: User
) -> AgentConversation:
    conv = db.get(AgentConversation, conversation_id)
    if conv is None or conv.created_by != user.id:
        raise NotFoundError("conversation not found", code="conversation_not_found")
    return conv


@router.post("/conversations", status_code=201, response_model=ConversationResponse)
def create_conversation(body: ConversationCreate, db: DbSession, user: CurrentUser):
    conv = AgentConversation(title=body.title, created_by=user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return ConversationResponse.model_validate(conv)


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(db: DbSession, user: CurrentUser):
    rows = db.execute(
        select(AgentConversation)
        .where(AgentConversation.created_by == user.id)
        .order_by(AgentConversation.created_at.desc())
    ).scalars()
    return [ConversationResponse.model_validate(c) for c in rows]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return ConversationDetail.model_validate(_get_own_conversation(db, conversation_id, user))


@router.post(
    "/conversations/{conversation_id}/messages", status_code=201, response_model=MessageResponse
)
def add_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    db: DbSession,
    user: CurrentUser,
):
    conv = _get_own_conversation(db, conversation_id, user)
    msg = AgentMessage(conversation_id=conv.id, role=body.role, content=body.content)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return MessageResponse.model_validate(msg)
