from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
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
    """Create a new shortcut message. Key must be unique per user."""
    # Check if key already exists for THIS user
    existing = (
        db.query(ShortcutMessage)
        .filter(ShortcutMessage.key == data.key, ShortcutMessage.created_by == user_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Shortcut with key '{data.key}' already exists in your shortcuts",
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
        # Check if new key conflicts with another shortcut owned by same user
        existing = (
            db.query(ShortcutMessage)
            .filter(
                ShortcutMessage.key == data.key,
                ShortcutMessage.id != shortcut_id,
                ShortcutMessage.created_by == shortcut.created_by,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Shortcut with key '{data.key}' already exists in your shortcuts",
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


def duplicate_shortcut(
    shortcut_id: int, user_id: int, db: Session
) -> ShortcutMessageResponse:
    """Duplicate another agent's shortcut into the current user's own shortcuts."""
    source = (
        db.query(ShortcutMessage)
        .options(joinedload(ShortcutMessage.creator))
        .filter(ShortcutMessage.id == shortcut_id)
        .first()
    )
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shortcut not found",
        )

    if source.created_by == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot duplicate your own shortcut",
        )

    # Check if user already has a shortcut with the same key
    existing = (
        db.query(ShortcutMessage)
        .filter(ShortcutMessage.key == source.key, ShortcutMessage.created_by == user_id)
        .first()
    )
    if existing:
        return _to_response(existing)

    new_shortcut = ShortcutMessage(
        key=source.key,
        values=source.values,
        created_by=user_id,
    )
    db.add(new_shortcut)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Old global unique constraint still in DB (migration not yet run).
        # Return existing shortcut for this user if found, else surface error.
        existing = (
            db.query(ShortcutMessage)
            .options(joinedload(ShortcutMessage.creator))
            .filter(ShortcutMessage.key == source.key, ShortcutMessage.created_by == user_id)
            .first()
        )
        if existing:
            return _to_response(existing)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Shortcut with key '{source.key}' already exists. Run alembic upgrade head to allow per-user keys.",
        )
    db.refresh(new_shortcut)

    new_shortcut = (
        db.query(ShortcutMessage)
        .options(joinedload(ShortcutMessage.creator))
        .filter(ShortcutMessage.id == new_shortcut.id)
        .first()
    )
    return _to_response(new_shortcut)


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
