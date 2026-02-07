from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ShortcutMessageCreate(BaseModel):
    key: str
    values: str


class ShortcutMessageUpdate(BaseModel):
    key: Optional[str] = None
    values: Optional[str] = None


class ShortcutMessageResponse(BaseModel):
    id: int
    key: str
    values: str
    created_by: int
    creator_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
