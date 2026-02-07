from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.models.shortcut_message import ShortcutMessage
from app.models.user import User
from app.schemas.shortcut_schema import (
    ShortcutMessageCreate,
    ShortcutMessageUpdate,
    ShortcutMessageResponse,
)
from typing import List


def _to_response(shortcut: ShortcutMessage) -> ShortcutMessageResponse:
    """Convert model to response schema with creator name."""
    return ShortcutMessageResponse(
        id=shortcut.id,
        key=shortcut.key,
        values=shortcut.values,
        created_by=shortcut.created_by,
        creator_name=shortcut.creator.name if shortcut.creator else None,
        created_at=shortcut.created_at,
        updated_at=shortcut.updated_at,
    )


def get_all_shortcuts(db: Session) -> List[ShortcutMessageResponse]:
    """Get all shortcut messages."""
    shortcuts = (
        db.query(ShortcutMessage)
        .options(joinedload(ShortcutMessage.creator))
        .order_by(ShortcutMessage.key)
        .all()
    )
    return [_to_response(s) for s in shortcuts]


def get_shortcut_by_id(shortcut_id: int, db: Session) -> ShortcutMessageResponse:
    """Get a single shortcut by ID."""
    shortcut = (
        db.query(ShortcutMessage)
        .options(joinedload(ShortcutMessage.creator))
        .filter(ShortcutMessage.id == shortcut_id)
        .first()
    )
    if not shortcut:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shortcut not found",
        )
    return _to_response(shortcut)


def search_shortcuts(keyword: str, db: Session) -> List[ShortcutMessageResponse]:
    """Search shortcuts by key (for auto-suggest, e.g. typing '/' shows list)."""
    shortcuts = (
        db.query(ShortcutMessage)
        .options(joinedload(ShortcutMessage.creator))
        .filter(ShortcutMessage.key.ilike(f"%{keyword}%"))
        .order_by(ShortcutMessage.key)
        .all()
    )
    return [_to_response(s) for s in shortcuts]


def create_shortcut(
    data: ShortcutMessageCreate, user_id: int, db: Session
) -> ShortcutMessageResponse:
    """Create a new shortcut message."""
    # Check if key already exists
    existing = (
        db.query(ShortcutMessage)
        .filter(ShortcutMessage.key == data.key)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Shortcut with key '{data.key}' already exists",
        )

    shortcut = ShortcutMessage(
        key=data.key,
        values=data.values,
        created_by=user_id,
    )
    db.add(shortcut)
    db.commit()
    db.refresh(shortcut)

    # Reload with creator relationship
    shortcut = (
        db.query(ShortcutMessage)
        .options(joinedload(ShortcutMessage.creator))
        .filter(ShortcutMessage.id == shortcut.id)
        .first()
    )
    return _to_response(shortcut)


def update_shortcut(
    shortcut_id: int, data: ShortcutMessageUpdate, db: Session
) -> ShortcutMessageResponse:
    """Update an existing shortcut message."""
    shortcut = (
        db.query(ShortcutMessage)
        .options(joinedload(ShortcutMessage.creator))
        .filter(ShortcutMessage.id == shortcut_id)
        .first()
    )
    if not shortcut:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shortcut not found",
        )

    if data.key is not None:
        # Check if new key conflicts with another shortcut
        existing = (
            db.query(ShortcutMessage)
            .filter(ShortcutMessage.key == data.key, ShortcutMessage.id != shortcut_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Shortcut with key '{data.key}' already exists",
            )
        shortcut.key = data.key

    if data.values is not None:
        shortcut.values = data.values

    db.commit()
    db.refresh(shortcut)

    # Reload with creator
    shortcut = (
        db.query(ShortcutMessage)
        .options(joinedload(ShortcutMessage.creator))
        .filter(ShortcutMessage.id == shortcut.id)
        .first()
    )
    return _to_response(shortcut)


def delete_shortcut(shortcut_id: int, db: Session):
    """Delete a shortcut message."""
    shortcut = (
        db.query(ShortcutMessage)
        .filter(ShortcutMessage.id == shortcut_id)
        .first()
    )
    if not shortcut:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shortcut not found",
        )

    db.delete(shortcut)
    db.commit()

    return {"message": "Shortcut deleted successfully"}
