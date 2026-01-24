#!/usr/bin/env python3
"""
Test script untuk simulate 4 customer chat masuk bersamaan
dan auto-assign ke 4 agent berbeda
"""
import requests
import time
import threading
import sys
import os
from typing import List, Dict

# Add app to path for direct database access
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.database import SessionLocal
from app.models.ticket import Ticket
from app.models.chat import Chat
from app.models.user import User, UserRole
from app.models.agent_profile import AgentProfile
from sqlalchemy.orm import joinedload

# Baileys webhook URL
WEBHOOK_URL = "http://localhost:8000/webhook/baileys"
BASE_URL = "http://localhost:8000"

# Simulate 4 different customers
customers = [
    {
        "from": "628111111111@c.us",
        "pushName": "Customer 1",
        "text": "agent",  # Request agent immediately
    },
    {
        "from": "628222222222@c.us",
        "pushName": "Customer 2",
        "text": "agent",
    },
    {
        "from": "628333333333@c.us",
        "pushName": "Customer 3",
        "text": "agent",
    },
    {
        "from": "628444444444@c.us",
        "pushName": "Customer 4",
        "text": "agent",
    },
]


def send_message(customer: Dict, results: List):
    """Send message to webhook (thread-safe)"""
    payload = {
        "messages": [
            {
                "from": customer["from"],
                "pushname": customer["pushName"],
                "text": customer["text"],
                "timestamp": int(time.time()),
                "messageId": f"test_{customer['from']}_{int(time.time())}",
            }
        ]
    }

    try:
        print(f"📤 Sending message from {customer['pushName']} ({customer['from']})...")
        response = requests.post(WEBHOOK_URL, json=payload, timeout=10.0)
        result = response.json()
        print(f"✅ {customer['pushName']}: {result}")
        results.append((customer, result))
    except Exception as e:
        print(f"❌ Error for {customer['pushName']}: {e}")
        results.append((customer, None))


def main():
    print("=" * 60)
    print("🧪 TEST: Auto-assign 4 customers to 4 agents")
    print("=" * 60)
    print()

    # Ensure backend is running
    try:
        requests.get(f"{BASE_URL}/", timeout=5.0)
        print("✅ Backend is running")
    except Exception:
        print("❌ Backend is not running. Start it first!")
        print("   cd /Users/mm/Desktop/Dashboard/project-root/backend-dashboard-python")
        print("   uvicorn app.main:app --reload")
        return

    # Check available agents
    print("🔍 Checking available agents...")
    agents = []
    try:
        response = requests.get(f"{BASE_URL}/users", timeout=5.0)
        users = response.json()
        agents = [u for u in users if u.get("role") == "agent"]

        print(f"\n{'='*60}")
        print(f"📋 AGENT LIST ({len(agents)} agents)")
        print(f"{'='*60}")

        for i, agent in enumerate(agents, 1):
            status_emoji = "🟢" if agent.get("is_online") else "⚪"
            print(f"  {i}. {status_emoji} Agent #{agent.get('id')}: {agent.get('name')} ({agent.get('email')})")

        print(f"{'='*60}\n")

        if len(agents) < 4:
            print(f"⚠️  WARNING: Only {len(agents)} agents found. You need at least 4 agents for this test.")
            print("   Create more agents in the admin panel first.")
            print("   Continuing anyway to test with available agents...\n")
    except Exception as e:
        print(f"⚠️  Could not verify agents: {e}")
        print("   Continuing anyway...\n")

    print("Sending 4 messages simultaneously...\n")

    # Send all messages concurrently using threads
    results = []
    threads = []

    for customer in customers:
        thread = threading.Thread(target=send_message, args=(customer, results))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    print("\n" + "=" * 60)
    print("📊 RESULTS:")
    print("=" * 60)

    for customer, result in results:
        if result:
            print(f"\n{customer['pushName']} ({customer['from']}):")
            print(f"  Mode: {result.get('mode', 'N/A')}")
            print(f"  Chat ID: {result.get('chat_id', 'N/A')}")
            print(f"  Message: {result.get('message', 'N/A')}")

    # Wait a bit for auto-assignment to complete
    print("\n⏳ Waiting 2 seconds for auto-assignment to complete...")
    time.sleep(2)

    # Query tickets directly from database
    print("\n📋 Fetching tickets from database...")
    try:
        db = SessionLocal()

        # Get test customer phones
        test_phones = [c["from"] for c in customers]

        # Find chats for test customers
        test_chats = db.query(Chat).filter(
            Chat.customer_phone.in_(test_phones)
        ).all()

        # Find tickets for these chats
        chat_ids = [chat.id for chat in test_chats]
        test_tickets = db.query(Ticket).options(
            joinedload(Ticket.assigned_agent)
        ).filter(
            Ticket.chat_id.in_(chat_ids)
        ).all()

        print(f"\n{'='*80}")
        print(f"📋 TICKET ASSIGNMENT RESULTS ({len(test_tickets)} tickets created)")
        print(f"{'='*80}")

        # Build agent ID to name mapping
        agent_map = {agent.get("id"): agent.get("name") for agent in agents}

        # Build chat ID to chat mapping
        chat_map = {chat.id: chat for chat in test_chats}

        for ticket in test_tickets:
            assigned = ticket.assigned_agent_id
            status_emoji = "✅" if assigned else "⏳"

            # Get customer info from chat
            chat = chat_map.get(ticket.chat_id)
            customer_name = chat.customer_name if chat else "Unknown"
            customer_phone = chat.customer_phone if chat else "N/A"

            if assigned:
                agent_name = ticket.assigned_agent.name if ticket.assigned_agent else f"Agent #{assigned}"
                status_text = f"🎯 {agent_name} (ID: {assigned})"
            else:
                status_text = "❌ UNASSIGNED (No available agent)"

            priority = ticket.priority.value.upper()
            print(
                f"\n  Ticket #{ticket.id}:"
            )
            print(f"    Customer   : {customer_name} ({customer_phone})")
            print(f"    Priority   : {priority}")
            print(f"    Status     : {status_text}")

        print(f"\n{'='*80}")

        if len(test_tickets) > 0:
            assigned_count = sum(1 for t in test_tickets if t.assigned_agent_id)
            total_count = len(test_tickets)

            print(f"\n📊 SUMMARY:")
            print(
                f"  ✅ Assigned  : {assigned_count}/{total_count} tickets "
                f"({int(assigned_count/total_count*100)}%)"
            )

            # Check if all assigned to different agents
            if assigned_count > 0:
                agent_ids = [
                    t.assigned_agent_id
                    for t in test_tickets
                    if t.assigned_agent_id
                ]
                unique_agents = len(set(agent_ids))
                print(f"  👥 Agents    : {unique_agents} unique agent(s) received tickets")

                # Show agent distribution
                from collections import Counter

                agent_distribution = Counter(agent_ids)
                print(f"\n  📈 Distribution per Agent:")
                for agent_id, count in sorted(
                    agent_distribution.items(), key=lambda x: x[1], reverse=True
                ):
                    # Get agent name from test_tickets
                    ticket_with_agent = next((t for t in test_tickets if t.assigned_agent_id == agent_id), None)
                    agent_name = ticket_with_agent.assigned_agent.name if ticket_with_agent and ticket_with_agent.assigned_agent else f"Agent #{agent_id}"
                    bar = "█" * count
                    print(f"     {agent_name:20} | {bar} ({count} ticket)")

                # Check fairness
                if len(agent_distribution) > 0:
                    max_tickets = max(agent_distribution.values())
                    min_tickets = min(agent_distribution.values())
                    if max_tickets == min_tickets:
                        print(f"\n  ✅ Perfect distribution - all agents got {max_tickets} ticket(s)")
                    else:
                        print(
                            f"\n  ⚠️  Uneven distribution - "
                            f"range from {min_tickets} to {max_tickets} ticket(s)"
                        )
        else:
            print("\n⚠️  No test tickets found. Check if chats were created properly.")

        print(f"\n{'='*80}")

        db.close()

    except Exception as e:
        print(f"❌ Could not fetch tickets: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("🎯 Check dashboard to verify:")
    print("   1. All 4 chats should be in agent mode")
    print("   2. Each chat should have a ticket created")
    print("   3. Tickets should be auto-assigned to available agents")
    print("   4. Each agent should get maximum 1 ticket if 4 agents available")
    print("=" * 60)


if __name__ == "__main__":
    main()
