"""
Seed script untuk membuat admin dan 5 agent
- Admin: username=admin, password=admin123
- Agent 1-5: username=agent1-5, password=agent123, phone=+6287731624016
"""

import sys
sys.path.insert(0, '.')

from sqlalchemy.orm import Session
from app.config.database import SessionLocal, engine
from app.models.user import User, UserRole
from app.models.agent_profile import AgentProfile, AgentStatus
from app.utils.security import hash_password


def seed_users():
    db: Session = SessionLocal()

    try:
        # Data untuk admin
        admin_data = {
            "name": "Administrator",
            "email": "admin@dashboard.com",
            "username": "admin",
            "password": hash_password("admin123"),
            "phone": "+6287731624016",
            "role": UserRole.admin
        }

        # Data untuk 5 agents
        agents_data = [
            {
                "name": "Agent 1",
                "email": "agent1@dashboard.com",
                "username": "agent1",
                "password": hash_password("agent123"),
                "phone": "+6287731624016",
                "role": UserRole.agent
            },
            {
                "name": "Agent 2",
                "email": "agent2@dashboard.com",
                "username": "agent2",
                "password": hash_password("agent123"),
                "phone": "+6287731624016",
                "role": UserRole.agent
            },
            {
                "name": "Agent 3",
                "email": "agent3@dashboard.com",
                "username": "agent3",
                "password": hash_password("agent123"),
                "phone": "+6287731624016",
                "role": UserRole.agent
            },
            {
                "name": "Agent 4",
                "email": "agent4@dashboard.com",
                "username": "agent4",
                "password": hash_password("agent123"),
                "phone": "+6287731624016",
                "role": UserRole.agent
            },
            {
                "name": "Agent 5",
                "email": "agent5@dashboard.com",
                "username": "agent5",
                "password": hash_password("agent123"),
                "phone": "+6287731624016",
                "role": UserRole.agent
            }
        ]

        # Cek dan buat admin
        existing_admin = db.query(User).filter(User.username == "admin").first()
        if existing_admin:
            print(f"Admin sudah ada (id={existing_admin.id}), skip...")
        else:
            admin = User(**admin_data)
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print(f"Admin berhasil dibuat: username=admin, password=admin123")

        # Buat 5 agents
        for i, agent_data in enumerate(agents_data, 1):
            username = f"agent{i}"
            existing_agent = db.query(User).filter(User.username == username).first()

            if existing_agent:
                print(f"Agent {i} sudah ada (id={existing_agent.id}), skip...")
                agent = existing_agent
            else:
                agent = User(**agent_data)
                db.add(agent)
                db.commit()
                db.refresh(agent)
                print(f"Agent {i} berhasil dibuat: username={username}, password=agent123")

            # Buat AgentProfile jika belum ada
            existing_profile = db.query(AgentProfile).filter(AgentProfile.user_id == agent.id).first()
            if not existing_profile:
                profile = AgentProfile(
                    user_id=agent.id,
                    display_name=f"Agent {i}",
                    signature=f"-Agent{i}",
                    status=AgentStatus.online,
                    is_available=True,
                    max_concurrent_tickets=5,
                    expertise_tags="general,support",
                    priority_score=i
                )
                db.add(profile)
                db.commit()
                print(f"  -> AgentProfile untuk Agent {i} dibuat (status=online, available=true)")
            else:
                # Update profile ke online
                existing_profile.status = AgentStatus.online
                existing_profile.is_available = True
                db.commit()
                print(f"  -> AgentProfile untuk Agent {i} sudah ada, set ke online")

        print("\n" + "="*50)
        print("SELESAI! User yang dibuat:")
        print("="*50)
        print("ADMIN:")
        print("  - Username: admin")
        print("  - Password: admin123")
        print("  - Phone: +6287731624016")
        print("\nAGENTS:")
        for i in range(1, 6):
            print(f"  - Username: agent{i}")
            print(f"    Password: agent123")
            print(f"    Phone: +6287731624016")
        print("="*50)

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_users()
