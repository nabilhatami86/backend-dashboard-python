from fastapi import APIRouter, Depends, Header, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.schemas.shortcut_schema import (
    ShortcutMessageCreate,
    ShortcutMessageUpdate,
    ShortcutMessageResponse,
)
from app.controller.shortcut_controller import (
    get_all_shortcuts,
    get_shortcut_by_id,
    search_shortcuts,
    create_shortcut,
    update_shortcut,
    delete_shortcut,
    duplicate_shortcut,
)
from app.config.deps import get_db
from app.utils.jwt import decode_access_token

router = APIRouter(
    prefix="/shortcuts",
    tags=["Shortcuts"],
)


def get_current_user(authorization: Optional[str] = Header(None)):
    """Extract user from JWT token."""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.split(" ")[1]
    payload = decode_access_token(token)

    if not payload:
        return None

    return {
        "id": int(payload.get("sub")),
        "role": payload.get("role"),
    }


@router.get("/", response_model=List[ShortcutMessageResponse])
def list_shortcuts(db: Session = Depends(get_db)):
    """Get all shortcut messages."""
    return get_all_shortcuts(db)


@router.get("/search", response_model=List[ShortcutMessageResponse])
def search_shortcut_messages(
    q: str = Query(..., description="Search keyword for shortcut key"),
    db: Session = Depends(get_db),
):
    """Search shortcuts by key (for auto-suggest when typing '/')."""
    return search_shortcuts(q, db)


@router.get("/{shortcut_id}", response_model=ShortcutMessageResponse)
def get_shortcut(shortcut_id: int, db: Session = Depends(get_db)):
    """Get a single shortcut by ID."""
    return get_shortcut_by_id(shortcut_id, db)


@router.post("/", response_model=ShortcutMessageResponse)
def create_shortcut_message(
    data: ShortcutMessageCreate,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Create a new shortcut message (auth required)."""
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return create_shortcut(data, user["id"], db)


@router.patch("/{shortcut_id}", response_model=ShortcutMessageResponse)
def update_shortcut_message(
    shortcut_id: int,
    data: ShortcutMessageUpdate,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Update a shortcut message (auth required)."""
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return update_shortcut(shortcut_id, data, db)


@router.post("/{shortcut_id}/duplicate", response_model=ShortcutMessageResponse)
def duplicate_shortcut_message(
    shortcut_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Duplicate another agent's shortcut into current user's own shortcuts."""
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return duplicate_shortcut(shortcut_id, user["id"], db)


@router.delete("/{shortcut_id}")
def delete_shortcut_message(
    shortcut_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Delete a shortcut message (auth required)."""
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return delete_shortcut(shortcut_id, db)
