from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.schemas.chat_schema import (
    ChatCreate,
    ChatUpdate,
    ChatResponse,
    ChatListResponse,
    MessageCreate,
    MessageResponse
)
from app.controller.chat_controller import (
    get_all_chats,
    get_chat_detail,
    create_chat,
    update_chat,
    send_message,
    mark_messages_as_read,
    delete_chat,
    update_message,
    delete_message
)
from app.config.deps import get_db
from app.utils.jwt import decode_access_token

router = APIRouter(
    prefix="/chats",
    tags=["Chats"]
)


def get_current_user(authorization: Optional[str] = Header(None)):
    """Extract user from JWT token"""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.split(" ")[1]
    payload = decode_access_token(token)

    if not payload:
        return None

    return {
        "id": int(payload.get("sub")),
        "role": payload.get("role")
    }


@router.get("/", response_model=List[ChatListResponse])
def list_chats(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """Get all chats"""
    user = get_current_user(authorization)
    user_id = user.get("id") if user else None
    user_role = user.get("role") if user else None

    return get_all_chats(db, user_id, user_role)


@router.get("/{chat_id}", response_model=ChatResponse)
def get_chat(chat_id: int, db: Session = Depends(get_db)):
    """Get chat detail with messages"""
    return get_chat_detail(chat_id, db)


@router.post("/", response_model=ChatResponse)
def create_new_chat(data: ChatCreate, db: Session = Depends(get_db)):
    """Create new chat"""
    return create_chat(data, db)


@router.patch("/{chat_id}", response_model=ChatResponse)
def update_chat_data(chat_id: int, data: ChatUpdate, db: Session = Depends(get_db)):
    """Update chat (assign agent, change mode, etc)"""
    return update_chat(chat_id, data, db)


@router.post("/messages", response_model=MessageResponse)
def send_chat_message(
    data: MessageCreate,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """Send a message"""
    user = get_current_user(authorization)

    # If sender is agent and we have user info, attach agent_id
    if data.sender == "agent" and user:
        data.agent_id = user.get("id")

    return send_message(data, db)


@router.post("/{chat_id}/read")
def mark_chat_as_read(chat_id: int, db: Session = Depends(get_db)):
    """Mark all messages in chat as read"""
    return mark_messages_as_read(chat_id, db)


@router.delete("/{chat_id}")
def delete_chat_endpoint(
    chat_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """Delete a chat and all its messages"""
    user = get_current_user(authorization)

    # Only admin can delete chats
    if not user or user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete chats"
        )

    return delete_chat(chat_id, db)


@router.patch("/messages/{message_id}")
def update_message_endpoint(
    message_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    """Update/edit a message"""
    new_text = data.get("text")
    if not new_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text is required"
        )

    return update_message(message_id, new_text, db)


@router.delete("/messages/{message_id}")
def delete_message_endpoint(
    message_id: int,
    db: Session = Depends(get_db)
):
    """Delete a message"""
    return delete_message(message_id, db)
