from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.user import User, UserRole
from app.models.agent_profile import AgentProfile, AgentStatus
from app.utils.security import hash_password


def get_all_admins(db: Session):
    admins = db.query(User).filter(User.role == UserRole.admin).all()
    return [
        {
            "id": admin.id,
            "name": admin.name,
            "email": admin.email,
            "phone": admin.phone,
            "username": admin.username,
            "role": admin.role.value,
            "online": False,
        }
        for admin in admins
    ]


def get_all_agents(db: Session):
    agents = db.query(User).filter(User.role == UserRole.agent).all()
    result = []
    for agent in agents:
        profile = db.query(AgentProfile).filter(AgentProfile.user_id == agent.id).first()
        result.append({
            "id": agent.id,
            "name": agent.name,
            "email": agent.email,
            "phone": agent.phone,
            "username": agent.username,
            "role": agent.role.value,
            "display_name": profile.display_name if profile else agent.name,
            "status": profile.status.value if profile else "offline",
            "is_available": profile.is_available if profile else False,
        })
    return result


def create_agent(data: dict, db: Session):
    """Buat agent baru + auto-create AgentProfile"""
    if db.query(User).filter(User.email == data["email"]).first():
        raise HTTPException(status_code=400, detail="Email sudah digunakan")
    if db.query(User).filter(User.username == data["username"]).first():
        raise HTTPException(status_code=400, detail="Username sudah digunakan")

    password = data.get("password", "").strip()
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password minimal 6 karakter")

    user = User(
        name=data["name"],
        email=data["email"],
        username=data["username"],
        password=hash_password(password),
        phone=data.get("phone"),
        role=UserRole.agent,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    display_name = data.get("display_name") or data["name"]
    profile = AgentProfile(
        user_id=user.id,
        display_name=display_name,
        status=AgentStatus.offline,
        is_available=False,
    )
    db.add(profile)
    db.commit()

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "username": user.username,
        "phone": user.phone,
        "role": user.role.value,
        "display_name": display_name,
        "status": "offline",
        "is_available": False,
    }


def update_agent_full(user_id: int, data: dict, db: Session):
    """Edit semua field agent"""
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.agent).first()
    if not user:
        raise HTTPException(status_code=404, detail="Agent tidak ditemukan")

    if "name" in data and data["name"]:
        user.name = data["name"]
    if "email" in data and data["email"]:
        existing = db.query(User).filter(User.email == data["email"], User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email sudah digunakan")
        user.email = data["email"]
    if "username" in data and data["username"]:
        existing = db.query(User).filter(User.username == data["username"], User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username sudah digunakan")
        user.username = data["username"]
    if "phone" in data:
        user.phone = data["phone"]
    if "password" in data and data["password"]:
        pw = data["password"].strip()
        if len(pw) < 6:
            raise HTTPException(status_code=400, detail="Password minimal 6 karakter")
        user.password = hash_password(pw)

    db.commit()
    db.refresh(user)

    profile = db.query(AgentProfile).filter(AgentProfile.user_id == user_id).first()
    if not profile:
        profile = AgentProfile(user_id=user_id, display_name=data.get("display_name") or user.name)
        db.add(profile)
    elif "display_name" in data and data["display_name"]:
        profile.display_name = data["display_name"]
    db.commit()
    db.refresh(profile)

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "username": user.username,
        "phone": user.phone,
        "role": user.role.value,
        "display_name": profile.display_name,
        "status": profile.status.value,
        "is_available": profile.is_available,
    }


def delete_agent(user_id: int, db: Session):
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.agent).first()
    if not user:
        raise HTTPException(status_code=404, detail="Agent tidak ditemukan")
    db.delete(user)
    db.commit()
    return {"message": "Agent berhasil dihapus"}


def update_agent_tag(user_id: int, display_name: str, db: Session):
    """Agent ganti display name / tag miliknya sendiri"""
    display_name = display_name.strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="Display name tidak boleh kosong")

    profile = db.query(AgentProfile).filter(AgentProfile.user_id == user_id).first()
    if not profile:
        profile = AgentProfile(user_id=user_id, display_name=display_name)
        db.add(profile)
    else:
        profile.display_name = display_name
    db.commit()
    db.refresh(profile)
    return {"message": "Tag berhasil diperbarui", "display_name": profile.display_name}


def get_all_users(db: Session):
    users = db.query(User).all()
    return [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "username": user.username,
            "role": user.role.value,
            "online": False,
        }
        for user in users
    ]


def update_user_profile(user_id: int, data: dict, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if "name" in data and data["name"]:
        user.name = data["name"]
    if "email" in data and data["email"]:
        existing = db.query(User).filter(
            User.email == data["email"],
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already taken")
        user.email = data["email"]
    if "phone" in data:
        user.phone = data["phone"]

    db.commit()
    db.refresh(user)

    return {
        "message": "Profile updated successfully",
        "data": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "username": user.username,
            "role": user.role.value
        }
    }
