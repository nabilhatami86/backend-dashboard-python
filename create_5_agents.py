"""
Script untuk membuat 5 agent otomatis dengan konfigurasi:
- Nomor WhatsApp sama: +62 877 3162 4016 (WHAPI Channel: CATWMN-PVGDR)
- Username berbeda: agent1, agent2, agent3, agent4, agent5
- Password sama: agent123
- Display name berbeda untuk identifikasi
"""
from sqlalchemy.orm import Session
from app.config.database import SessionLocal
from app.models.user import User, UserRole
from app.models.agent_profile import AgentProfile, AgentStatus
from app.utils.security import hash_password


# Konfigurasi WHAPI
WHAPI_PHONE = "+62 877 3162 4016"
WHAPI_CHANNEL = "CATWMN-PVGDR"
DEFAULT_PASSWORD = "agent123"

# Data agent yang akan dibuat
AGENTS_DATA = [
    {
        "username": "agent1",
        "name": "Agent Satu",
        "email": "agent1@warungmadura.com",
        "display_name": "CS Warung Madura - Agent 1",
        "signature": "🙏 -Agent 1",
        "expertise_tags": "general,order,menu",
    },
    {
        "username": "agent2",
        "name": "Agent Dua",
        "email": "agent2@warungmadura.com",
        "display_name": "CS Warung Madura - Agent 2",
        "signature": "🙏 -Agent 2",
        "expertise_tags": "general,billing,complaint",
    },
    {
        "username": "agent3",
        "name": "Agent Tiga",
        "email": "agent3@warungmadura.com",
        "display_name": "CS Warung Madura - Agent 3",
        "signature": "🙏 -Agent 3",
        "expertise_tags": "general,delivery,tracking",
    },
    {
        "username": "agent4",
        "name": "Agent Empat",
        "email": "agent4@warungmadura.com",
        "display_name": "CS Warung Madura - Agent 4",
        "signature": "🙏 -Agent 4",
        "expertise_tags": "general,promotion,voucher",
    },
    {
        "username": "agent5",
        "name": "Agent Lima",
        "email": "agent5@warungmadura.com",
        "display_name": "CS Warung Madura - Agent 5",
        "signature": "🙏 -Agent 5",
        "expertise_tags": "general,technical,account",
    },
]


def create_agents():
    """Membuat 5 agent dengan konfigurasi yang sudah ditentukan"""
    db: Session = SessionLocal()

    print("=" * 70)
    print("🚀 Creating 5 Agents for Warung Madura")
    print("=" * 70)
    print(f"📱 WhatsApp Channel: {WHAPI_CHANNEL}")
    print(f"📞 Phone Number: {WHAPI_PHONE}")
    print(f"🔑 Password: {DEFAULT_PASSWORD}")
    print("=" * 70)

    try:
        created_count = 0
        skipped_count = 0
        hashed_password = hash_password(DEFAULT_PASSWORD)

        for agent_data in AGENTS_DATA:
            # Cek apakah user sudah ada
            existing_user = db.query(User).filter(
                User.username == agent_data["username"]
            ).first()

            if existing_user:
                print(f"\n⚠️  SKIPPED: {agent_data['username']} already exists")
                skipped_count += 1
                continue

            # Buat user baru
            new_user = User(
                name=agent_data["name"],
                email=agent_data["email"],
                username=agent_data["username"],
                password=hashed_password,
                phone=WHAPI_PHONE,  # Semua agent pakai nomor yang sama
                role=UserRole.agent
            )

            db.add(new_user)
            db.flush()  # Flush untuk mendapatkan user.id

            # Buat agent profile
            agent_profile = AgentProfile(
                user_id=new_user.id,
                display_name=agent_data["display_name"],
                signature=agent_data["signature"],
                status=AgentStatus.offline,
                is_available=False,
                max_concurrent_tickets=5,
                expertise_tags=agent_data["expertise_tags"],
                priority_score=0,
            )

            db.add(agent_profile)

            print(f"\n✅ CREATED: {agent_data['username']}")
            print(f"   Name: {agent_data['name']}")
            print(f"   Email: {agent_data['email']}")
            print(f"   Phone: {WHAPI_PHONE}")
            print(f"   Display Name: {agent_data['display_name']}")
            print(f"   Signature: {agent_data['signature']}")
            print(f"   Expertise: {agent_data['expertise_tags']}")

            created_count += 1

        # Commit semua perubahan
        db.commit()

        print("\n" + "=" * 70)
        print("🎉 Agent Creation Completed!")
        print("=" * 70)
        print(f"✅ Created: {created_count} agents")
        print(f"⚠️  Skipped: {skipped_count} agents (already exist)")
        print("=" * 70)

        if created_count > 0:
            print("\n📋 Login Credentials:")
            print("-" * 70)
            for agent_data in AGENTS_DATA:
                print(f"Username: {agent_data['username']} | Password: {DEFAULT_PASSWORD}")
            print("-" * 70)

            print("\nℹ️  Notes:")
            print("   • Semua agent menggunakan nomor WhatsApp yang sama")
            print("   • Setiap agent memiliki display name & signature berbeda")
            print("   • Default status: offline, is_available: false")
            print("   • Max concurrent tickets: 5 per agent")

    except Exception as e:
        print(f"\n❌ Error creating agents: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def show_all_agents():
    """Tampilkan semua agent yang ada di database"""
    db: Session = SessionLocal()

    try:
        agents = db.query(User).filter(User.role == UserRole.agent).all()

        if not agents:
            print("⚠️  No agents found in database")
            return

        print(f"\n📋 Current Agents in Database ({len(agents)}):")
        print("=" * 70)

        for idx, agent in enumerate(agents, 1):
            profile = db.query(AgentProfile).filter(
                AgentProfile.user_id == agent.id
            ).first()

            print(f"\n{idx}. {agent.username}")
            print(f"   Name: {agent.name}")
            print(f"   Email: {agent.email}")
            print(f"   Phone: {agent.phone}")

            if profile:
                print(f"   Display Name: {profile.display_name}")
                print(f"   Signature: {profile.signature}")
                print(f"   Status: {profile.status.value}")
                print(f"   Available: {profile.is_available}")

        print("\n" + "=" * 70)

    except Exception as e:
        print(f"❌ Error fetching agents: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    # Cek argumen
    if "--show" in sys.argv or "-s" in sys.argv:
        show_all_agents()
        sys.exit(0)

    # Jalankan pembuatan agent
    create_agents()

    # Tampilkan semua agent setelah dibuat
    show_all_agents()
