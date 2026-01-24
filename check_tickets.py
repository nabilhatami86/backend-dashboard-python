#!/usr/bin/env python3
"""
Quick script to check tickets in database directly
"""
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.database import SessionLocal
from app.models.ticket import Ticket
from app.models.chat import Chat
from sqlalchemy.orm import joinedload

def main():
    db = SessionLocal()

    try:
        # Get test customer phones
        test_phones = [
            "628111111111@c.us",
            "628222222222@c.us",
            "628333333333@c.us",
            "628444444444@c.us",
        ]

        print("=" * 80)
        print("🔍 CHECKING TICKETS IN DATABASE")
        print("=" * 80)

        # Find chats for test customers
        test_chats = db.query(Chat).filter(
            Chat.customer_phone.in_(test_phones)
        ).all()

        print(f"\n📋 Found {len(test_chats)} test chats:")
        for chat in test_chats:
            print(f"  - Chat #{chat.id}: {chat.customer_name} ({chat.customer_phone}) - Mode: {chat.mode.value}")

        # Find tickets for these chats
        chat_ids = [chat.id for chat in test_chats]
        tickets = db.query(Ticket).options(
            joinedload(Ticket.assigned_agent)
        ).filter(
            Ticket.chat_id.in_(chat_ids)
        ).all()

        print(f"\n🎫 Found {len(tickets)} tickets for test chats:")
        print("=" * 80)

        if tickets:
            for ticket in tickets:
                chat = next((c for c in test_chats if c.id == ticket.chat_id), None)
                customer_name = chat.customer_name if chat else "Unknown"
                customer_phone = chat.customer_phone if chat else "N/A"

                agent_name = ticket.assigned_agent.name if ticket.assigned_agent else "UNASSIGNED"
                agent_id = ticket.assigned_agent_id or "None"

                print(f"\nTicket #{ticket.id}:")
                print(f"  Chat ID    : {ticket.chat_id}")
                print(f"  Customer   : {customer_name} ({customer_phone})")
                print(f"  Priority   : {ticket.priority.value}")
                print(f"  Status     : {ticket.status.value}")
                print(f"  Agent      : {agent_name} (ID: {agent_id})")
                print(f"  Created    : {ticket.created_at}")
        else:
            print("\n⚠️  No tickets found for test chats!")
            print("\nPossible reasons:")
            print("1. ensure_ticket_exists() wasn't called")
            print("2. Database transaction didn't commit")
            print("3. Tickets were created but deleted")

        print("\n" + "=" * 80)

        # Show all tickets in system
        all_tickets = db.query(Ticket).all()
        print(f"\n📊 Total tickets in system: {len(all_tickets)}")

    finally:
        db.close()

if __name__ == "__main__":
    main()
