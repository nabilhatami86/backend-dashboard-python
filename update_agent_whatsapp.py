"""
Script untuk update nomor WhatsApp semua agent ke nomor yang terdaftar di WHAPI
Channel: CATWMN-PVGDR
Nomor: +62 877 3162 4016
"""
from sqlalchemy.orm import Session
from app.config.database import SessionLocal
from app.models.user import User, UserRole


def update_agent_whatsapp_numbers():
    """
    Update semua agent dengan nomor WhatsApp yang terdaftar di WHAPI
    Semua agent akan menggunakan 1 nomor WhatsApp yang sama (multi-agent single number)
    """
    db: Session = SessionLocal()

    # Nomor WhatsApp yang terdaftar di WHAPI
    WHAPI_PHONE_NUMBER = "+62 877 3162 4016"
    WHAPI_CHANNEL = "CATWMN-PVGDR"

    try:
        # Ambil semua user dengan role agent
        agents = db.query(User).filter(User.role == UserRole.agent).all()

        if not agents:
            print("⚠️  Tidak ada agent yang ditemukan di database")
            return

        print(f"\n📱 Updating {len(agents)} agent(s) dengan nomor WHAPI:")
        print(f"   Channel: {WHAPI_CHANNEL}")
        print(f"   Nomor: {WHAPI_PHONE_NUMBER}\n")

        # Update setiap agent
        updated_count = 0
        for agent in agents:
            old_phone = agent.phone
            agent.phone = WHAPI_PHONE_NUMBER
            updated_count += 1

            if old_phone != WHAPI_PHONE_NUMBER:
                print(f"✅ Updated: {agent.name} ({agent.username})")
                print(f"   Old: {old_phone or 'None'}")
                print(f"   New: {WHAPI_PHONE_NUMBER}\n")
            else:
                print(f"ℹ️  Unchanged: {agent.name} ({agent.username}) - already has correct number\n")

        # Commit changes
        db.commit()

        print(f"\n🎉 Update completed!")
        print(f"   Total agents updated: {updated_count}")
        print(f"   Semua agent sekarang menggunakan nomor: {WHAPI_PHONE_NUMBER}")
        print(f"   Channel WHAPI: {WHAPI_CHANNEL}")
        print("\nℹ️  Catatan: Semua agent menggunakan 1 nomor WhatsApp yang sama.")
        print("   Setiap agent akan memiliki signature/display name berbeda dalam pesan.")

    except Exception as e:
        print(f"❌ Error updating agent phone numbers: {e}")
        db.rollback()
    finally:
        db.close()


def show_current_agents():
    """Tampilkan daftar agent saat ini beserta nomor WhatsApp mereka"""
    db: Session = SessionLocal()

    try:
        agents = db.query(User).filter(User.role == UserRole.agent).all()

        if not agents:
            print("⚠️  Tidak ada agent yang ditemukan di database")
            return

        print(f"\n📋 Current Agents ({len(agents)}):")
        print("=" * 70)
        for idx, agent in enumerate(agents, 1):
            print(f"{idx}. {agent.name}")
            print(f"   Username: {agent.username}")
            print(f"   Email: {agent.email}")
            print(f"   Phone: {agent.phone or 'Not set'}")
            print("-" * 70)

    except Exception as e:
        print(f"❌ Error fetching agents: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    print("=" * 70)
    print("🔧 Agent WhatsApp Number Update Tool")
    print("=" * 70)

    # Tampilkan agent saat ini
    show_current_agents()

    # Cek argumen
    auto_confirm = "--yes" in sys.argv or "-y" in sys.argv

    if not auto_confirm:
        # Konfirmasi update
        print("\n⚠️  WARNING: This will update ALL agents to use the WHAPI registered number:")
        print(f"   Channel: CATWMN-PVGDR")
        print(f"   Number: +62 877 3162 4016")

        try:
            response = input("\nProceed with update? (yes/no): ").strip().lower()
        except EOFError:
            print("\n❌ No input received. Use --yes flag for non-interactive mode")
            sys.exit(1)

        if response != "yes":
            print("\n❌ Update cancelled")
            sys.exit(0)

    # Lakukan update
    update_agent_whatsapp_numbers()
