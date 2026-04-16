from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.auth_schema import RegisterSchema, LoginSchema
from app.controller.auth_controller import register_user, login_user
from app.config.deps import get_db, get_current_user
from app.models.user import User, UserRole
from app.models.agent_profile import AgentProfile, AgentStatus
from app.services.ws_manager import manager as ws_manager
from datetime import datetime

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

@router.post("/register")
def register(data: RegisterSchema, db: Session = Depends(get_db)):
    return register_user(data, db)

@router.post("/login")
async def login(data: LoginSchema, db: Session = Depends(get_db)):
    result = login_user(data, db)

    # Broadcast status online ke semua dashboard client jika agent
    user_role = result["data"]["role"]
    if user_role == "agent":
        agent_profile = db.query(AgentProfile).filter(
            AgentProfile.user_id == result["data"]["id"]
        ).first()
        if agent_profile:
            await ws_manager.broadcast_global({
                "type": "agent_status",
                "agent_id": result["data"]["id"],
                "name": result["data"]["name"],
                "display_name": agent_profile.display_name,
                "status": "online",
                "is_available": True,
            })

    return result

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout: jika agent, set status offline dan broadcast ke semua client.
    """
    if current_user.role == UserRole.agent:
        agent_profile = db.query(AgentProfile).filter(
            AgentProfile.user_id == current_user.id
        ).first()

        if agent_profile:
            agent_profile.status = AgentStatus.offline
            agent_profile.is_available = False
            agent_profile.last_activity_at = datetime.now()
            db.commit()

            await ws_manager.broadcast_global({
                "type": "agent_status",
                "agent_id": current_user.id,
                "name": current_user.name,
                "display_name": agent_profile.display_name,
                "status": "offline",
                "is_available": False,
            })

    return {"message": "Logout success"}
