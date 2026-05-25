from fastapi import APIRouter, Depends, Header, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
from datetime import datetime
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
    delete_message,
    get_available_tickets,
    claim_ticket,
    update_tag_chat_agent
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


@router.patch("/messages/{message_id}/tag")
def update_tag_endpoint(
    message_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    """Update the ~ Agent Name tag on an agent message"""
    new_agent_name = data.get("agent_name")
    if not new_agent_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="agent_name is required"
        )
    return update_tag_chat_agent(message_id, new_agent_name, db)


# ================= TICKET QUEUE ENDPOINTS =================

@router.get("/queue/available", response_model=List[ChatResponse])
def get_ticket_queue(db: Session = Depends(get_db)):
    """
    Get all available tickets in the queue with full chat details and messages.

    Returns unassigned chats that agents can claim.
    Ordered by FIFO (First In First Out) - oldest chats first.
    """
    return get_available_tickets(db)


@router.post("/{chat_id}/claim", response_model=ChatResponse)
async def claim_ticket_endpoint(
    chat_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
):
    """
    Claim a ticket from the queue.
    Broadcasts ticket_claimed event so other agents remove it from their list immediately.
    """
    from app.services.ws_manager import manager as ws_manager

    user = get_current_user(authorization)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    if user.get("role") != "agent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only agents can claim tickets"
        )

    result = claim_ticket(chat_id, user.get("id"), db)

    # Broadcast ke semua agent agar yang lain langsung hapus chat ini dari list
    await ws_manager.broadcast_global({
        "type": "ticket_claimed",
        "chat_id": chat_id,
        "by_agent_id": user.get("id"),
    })

    return result


# ================= FILE UPLOAD ENDPOINT =================

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_DOC_TYPES = {
    "application/pdf", "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain", "application/zip",
}
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10MB
MAX_DOC_SIZE = 25 * 1024 * 1024     # 25MB


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Upload a file (image or document) for chat messages"""
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    content_type = file.content_type or ""
    is_image = content_type in ALLOWED_IMAGE_TYPES
    is_doc = content_type in ALLOWED_DOC_TYPES

    if not is_image and not is_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed: {content_type}",
        )

    # Read file content
    content = await file.read()
    max_size = MAX_IMAGE_SIZE if is_image else MAX_DOC_SIZE
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max size: {max_size // (1024*1024)}MB",
        )

    # Generate unique filename
    ext = os.path.splitext(file.filename or "file")[1] or (".jpg" if is_image else ".bin")
    unique_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as f:
        f.write(content)

    media_type = "image" if is_image else "document"

    return JSONResponse({
        "media_url": f"/uploads/{unique_name}",
        "media_type": media_type,
        "media_filename": file.filename or unique_name,
    })
