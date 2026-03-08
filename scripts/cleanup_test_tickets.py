#!/usr/bin/env python3
"""
Clean up test tickets and reset test chats to bot mode
"""
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.database import SessionLocal
from app.models.ticket import Ticket
from app.models.chat import Chat, ChatMode

def main():
    db = SessionLocal()

    try:
        # Test customer phones
        test_phones = [
            "628111111111@c.us",
            "628222222222@c.us",
            "628333333333@c.us",
            "628444444444@c.us",
        ]

        print("=" * 60)
        print("🧹 CLEANING UP TEST DATA")
        print("=" * 60)

        # Find test chats
        test_chats = db.query(Chat).filter(
            Chat.customer_phone.in_(test_phones)
        ).all()

        print(f"\n📋 Found {len(test_chats)} test chats")

        # Delete tickets for test chats
        chat_ids = [chat.id for chat in test_chats]
        tickets = db.query(Ticket).filter(
            Ticket.chat_id.in_(chat_ids)
        ).all()

        print(f"🎫 Found {len(tickets)} tickets to delete")

        for ticket in tickets:
            print(f"  ❌ Deleting ticket #{ticket.id}")
            db.delete(ticket)

        # Reset chats to bot mode
        for chat in test_chats:
            chat.mode = ChatMode.bot
            chat.assigned_agent_id = None
            print(f"  🔄 Reset chat #{chat.id} to bot mode")

        db.commit()

        print("\n" + "=" * 60)
        print("✅ Cleanup complete! Ready for fresh test.")
        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    main()
