from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
from app.models.user import User, UserRole
from app.models.agent_profile import AgentProfile, AgentStatus
from app.utils.security import hash_password, verify_password
from app.utils.jwt import create_access_token
from app.config_env import ACCESS_TOKEN_EXPIRE_MINUTES


def register_user(data, db: Session):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )
    user = User(
        name=data.name,
        email=data.email,
        username=data.username,
        password=hash_password(data.password),
        phone=data.phone,
        role=data.role
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "Register success",
            "data": {
                "id":user.id,
                "name":user.name,
                "username":user.username,
                "email":user.email,
                "phone":user.phone,
                "role": user.role.value

            }}


def login_user(data, db: Session):
    user = db.query(User).filter(
        or_(
            User.username == data.identifier,
            User.email == data.identifier
        )
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    if not verify_password(data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role.value
        },
        expires_minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # Jika user adalah agent, langsung set status online
    if user.role == UserRole.agent:
        agent_profile = db.query(AgentProfile).filter(
            AgentProfile.user_id == user.id
        ).first()

        if not agent_profile:
            # Auto-create profile jika belum ada
            agent_profile = AgentProfile(
                user_id=user.id,
                display_name=user.name,
            )
            db.add(agent_profile)

        agent_profile.status = AgentStatus.online
        agent_profile.is_available = True
        agent_profile.last_activity_at = datetime.now()
        db.commit()

    return {
        "message": "Login success",
        "data": {
            "id": user.id,
            "name": user.name,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "role": user.role.value
        },
        "access_token": token,
        "token_type": "bearer"
    }
