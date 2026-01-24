#!/usr/bin/env python3
"""
Set all agents to online status for testing
"""
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.database import SessionLocal
from app.models.user import User, UserRole
from app.models.agent_profile import AgentProfile, AgentStatus

def main():
    db = SessionLocal()

    try:
        # Get all agents
        agents = db.query(User).filter(User.role == UserRole.agent).all()

        print("=" * 60)
        print(f"🔧 SETTING {len(agents)} AGENTS TO ONLINE")
        print("=" * 60)

        for agent in agents:
            # Get or create agent profile
            profile = db.query(AgentProfile).filter(
                AgentProfile.user_id == agent.id
            ).first()

            if not profile:
                # Create profile if doesn't exist
                profile = AgentProfile(
                    user_id=agent.id,
                    display_name=agent.name,  # Use agent's name as display name
                    status=AgentStatus.online,
                    is_available=True,
                    max_concurrent_tickets=5,
                    priority_score=100
                )
                db.add(profile)
                print(f"  ✅ Created profile for Agent #{agent.id}: {agent.name}")
            else:
                # Update existing profile
                profile.status = AgentStatus.online
                profile.is_available = True
                print(f"  ✅ Set Agent #{agent.id}: {agent.name} to ONLINE")

        db.commit()

        print("\n" + "=" * 60)
        print("✅ All agents are now ONLINE and AVAILABLE")
        print("=" * 60)

        # Show current status
        print("\n📋 Current Agent Status:")
        for agent in agents:
            profile = db.query(AgentProfile).filter(
                AgentProfile.user_id == agent.id
            ).first()

            if profile:
                status_emoji = "🟢" if profile.status == AgentStatus.online else "⚪"
                avail_emoji = "✅" if profile.is_available else "❌"
                print(f"  {status_emoji} Agent #{agent.id}: {agent.name}")
                print(f"     Status: {profile.status.value} | Available: {avail_emoji} | Max tickets: {profile.max_concurrent_tickets}")

    finally:
        db.close()

if __name__ == "__main__":
    main()
