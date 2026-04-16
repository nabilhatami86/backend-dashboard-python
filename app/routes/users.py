from fastapi import APIRouter, Depends, Body, Header, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.controller.users_controller import (
    get_all_admins,
    get_all_agents,
    get_all_users,
    update_user_profile,
    create_agent,
    update_agent_full,
    delete_agent,
    update_agent_tag,
)
from app.config.deps import get_db
from app.utils.jwt import decode_access_token

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


def _get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"id": int(payload.get("sub")), "role": payload.get("role")}


def _require_admin(authorization: Optional[str] = Header(None)):
    user = _get_current_user(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@router.get("/admins")
def list_admins(db: Session = Depends(get_db)):
    return get_all_admins(db)


@router.get("/agents")
def list_agents(db: Session = Depends(get_db)):
    return get_all_agents(db)


@router.get("/")
def list_users(db: Session = Depends(get_db)):
    return get_all_users(db)


@router.post("/agents")
def create_agent_endpoint(
    data: dict = Body(...),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Admin: buat agent baru"""
    _require_admin(authorization)
    return create_agent(data, db)


@router.put("/agents/{user_id}")
def update_agent_endpoint(
    user_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Admin: edit semua field agent"""
    _require_admin(authorization)
    return update_agent_full(user_id, data, db)


@router.delete("/agents/{user_id}")
def delete_agent_endpoint(
    user_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Admin: hapus agent"""
    _require_admin(authorization)
    return delete_agent(user_id, db)


@router.patch("/agents/me/tag")
def update_my_tag(
    data: dict = Body(...),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Agent: edit tag (display_name) milik sendiri"""
    user = _get_current_user(authorization)
    display_name = data.get("display_name", "")
    return update_agent_tag(user["id"], display_name, db)


@router.patch("/{user_id}")
def update_profile(
    user_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db)
):
    """Update user profile (name, email, phone)"""
    return update_user_profile(user_id, data, db)
