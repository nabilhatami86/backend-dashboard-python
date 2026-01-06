"""
Test Script untuk WhatsApp Queue System
Test complete flow dari customer message sampai agent reply
"""
import requests
import json
from time import sleep

BASE_URL = "http://localhost:8000"

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_step(step, message):
    print(f"\n{Colors.BOLD}{Colors.BLUE}[Step {step}]{Colors.END} {message}")


def print_success(message):
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")


def print_error(message):
    print(f"{Colors.RED}✗ {message}{Colors.END}")


def print_info(message):
    print(f"{Colors.YELLOW}ℹ {message}{Colors.END}")


def test_webhook_customer_message():
    """Test 1: Simulate customer sending WhatsApp message"""
    print_step(1, "Customer sends WhatsApp message (simulated via webhook)")

    payload = {
        "messages": [{
            "from": "6281234567890@c.us",
            "from_name": "Test Customer",
            "text": {"body": "Halo, saya mau pesan nasi goreng"}
        }]
    }

    response = requests.post(f"{BASE_URL}/webhook/whapi/messages", json=payload)

    if response.status_code == 200:
        data = response.json()
        print_success(f"Webhook processed: {json.dumps(data, indent=2)}")
        return data.get("chat_id")
    else:
        print_error(f"Webhook failed: {response.status_code} - {response.text}")
        return None


def test_change_to_agent_mode(chat_id):
    """Test 2: Change chat mode to AGENT"""
    print_step(2, f"Change chat {chat_id} mode to AGENT")

    # Login as admin first
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "admin", "password": "admin123"}
    )

    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        print_success("Admin logged in")

        # Change chat mode
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.patch(
            f"{BASE_URL}/chats/{chat_id}",
            headers=headers,
            json={"mode": "agent"}
        )

        if response.status_code == 200:
            print_success(f"Chat mode changed to AGENT")
            return True
        else:
            print_error(f"Failed to change mode: {response.status_code} - {response.text}")
            return False
    else:
        print_error(f"Admin login failed: {login_response.status_code}")
        return False


def test_agent_login():
    """Test 3: Agent login and get token"""
    print_step(3, "Agent login")

    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "agent1", "password": "agent123"}
    )

    if response.status_code == 200:
        data = response.json()
        token = data["access_token"]
        user = data["user"]
        print_success(f"Agent logged in: {user['name']} (ID: {user['id']})")
        return token, user['id']
    else:
        print_error(f"Agent login failed: {response.status_code} - {response.text}")
        return None, None


def test_agent_set_online(token):
    """Test 4: Set agent status to online"""
    print_step(4, "Set agent status to ONLINE and AVAILABLE")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.patch(
        f"{BASE_URL}/agent/chats/status",
        headers=headers,
        json={"is_available": True, "status": "online"}
    )

    if response.status_code == 200:
        data = response.json()
        print_success(f"Agent status updated: {json.dumps(data, indent=2)}")
        return True
    else:
        print_error(f"Failed to update status: {response.status_code} - {response.text}")
        return False


def test_customer_message_in_agent_mode(chat_id):
    """Test 5: Customer sends another message (should create ticket)"""
    print_step(5, "Customer sends message in AGENT mode (should create ticket)")

    payload = {
        "messages": [{
            "from": "6281234567890@c.us",
            "from_name": "Test Customer",
            "text": {"body": "Berapa harga nasi gorengnya?"}
        }]
    }

    response = requests.post(f"{BASE_URL}/webhook/whapi/messages", json=payload)

    if response.status_code == 200:
        data = response.json()
        print_success(f"Message processed: {json.dumps(data, indent=2)}")
        print_info("Ticket should be auto-created and auto-assigned")
        return True
    else:
        print_error(f"Webhook failed: {response.status_code} - {response.text}")
        return False


def test_agent_get_chats(token):
    """Test 6: Agent get assigned chats"""
    print_step(6, "Agent retrieves assigned chats")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/agent/chats/my-chats", headers=headers)

    if response.status_code == 200:
        chats = response.json()
        print_success(f"Agent has {len(chats)} assigned chat(s)")
        for chat in chats:
            print_info(f"  Chat ID: {chat['id']}, Customer: {chat['customer_name']}, "
                      f"Ticket: {chat['ticket_id']}, Status: {chat['ticket_status']}")
        return chats
    else:
        print_error(f"Failed to get chats: {response.status_code} - {response.text}")
        return []


def test_agent_get_messages(token, chat_id):
    """Test 7: Agent get chat messages"""
    print_step(7, f"Agent retrieves messages from chat {chat_id}")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/agent/chats/chat/{chat_id}/messages",
        headers=headers
    )

    if response.status_code == 200:
        messages = response.json()
        print_success(f"Retrieved {len(messages)} message(s)")
        for msg in reversed(messages):  # Show oldest first
            sender = msg['sender']
            text = msg['text']
            print_info(f"  [{sender}]: {text}")
        return messages
    else:
        print_error(f"Failed to get messages: {response.status_code} - {response.text}")
        return []


def test_agent_send_reply(token, chat_id):
    """Test 8: Agent sends reply to customer"""
    print_step(8, "Agent sends reply to customer")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{BASE_URL}/agent/chats/send-message",
        headers=headers,
        json={
            "chat_id": chat_id,
            "text": "Halo! Harga nasi goreng special kami Rp 25.000. Ada yang bisa kami bantu lagi?"
        }
    )

    if response.status_code == 200:
        data = response.json()
        print_success("Reply sent successfully!")
        print_info(f"  Message to WhatsApp: {data.get('message')}")
        return True
    else:
        print_error(f"Failed to send reply: {response.status_code} - {response.text}")
        return False


def test_agent_get_status(token):
    """Test 9: Get agent status and statistics"""
    print_step(9, "Get agent status and statistics")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/agent/chats/status", headers=headers)

    if response.status_code == 200:
        data = response.json()
        print_success("Agent status retrieved:")
        print_info(f"  Display Name: {data['display_name']}")
        print_info(f"  Status: {data['status']}")
        print_info(f"  Available: {data['is_available']}")
        print_info(f"  Active Tickets: {data['active_tickets']}/{data['max_concurrent_tickets']}")
        print_info(f"  Total Handled: {data['total_tickets_handled']}")
        print_info(f"  Total Resolved: {data['total_tickets_resolved']}")
        return True
    else:
        print_error(f"Failed to get status: {response.status_code} - {response.text}")
        return False


def test_get_pending_tickets(token):
    """Test 10: Get pending tickets in queue"""
    print_step(10, "Get pending tickets in queue")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/tickets/queue", headers=headers)

    if response.status_code == 200:
        tickets = response.json()
        print_success(f"Found {len(tickets)} pending ticket(s) in queue")
        for ticket in tickets:
            print_info(f"  Ticket ID: {ticket['id']}, Priority: {ticket['priority']}, "
                      f"Customer: {ticket.get('customer_name', 'Unknown')}")
        return tickets
    else:
        print_error(f"Failed to get queue: {response.status_code} - {response.text}")
        return []


def test_resolve_ticket(token, chat_id):
    """Test 11: Resolve ticket"""
    print_step(11, f"Resolve ticket for chat {chat_id}")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{BASE_URL}/agent/chats/chat/{chat_id}/resolve",
        headers=headers
    )

    if response.status_code == 200:
        data = response.json()
        print_success(f"Ticket resolved: {json.dumps(data, indent=2)}")
        return True
    else:
        print_error(f"Failed to resolve: {response.status_code} - {response.text}")
        return False


def main():
    """Run complete flow test"""
    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}WhatsApp Queue System - Complete Flow Test{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}")

    print_info("Testing complete flow: Customer message → Ticket → Agent reply → Resolve")
    print_info(f"Base URL: {BASE_URL}")

    # Test flow
    chat_id = test_webhook_customer_message()
    if not chat_id:
        print_error("Flow stopped: Failed to create chat")
        return

    sleep(1)

    if not test_change_to_agent_mode(chat_id):
        print_error("Flow stopped: Failed to change to agent mode")
        return

    sleep(1)

    token, agent_id = test_agent_login()
    if not token:
        print_error("Flow stopped: Agent login failed")
        return

    sleep(1)

    if not test_agent_set_online(token):
        print_error("Flow stopped: Failed to set agent online")
        return

    sleep(1)

    if not test_customer_message_in_agent_mode(chat_id):
        print_error("Flow stopped: Failed to process customer message")
        return

    sleep(2)  # Give time for auto-assignment

    chats = test_agent_get_chats(token)
    if not chats:
        print_error("Warning: Agent has no assigned chats")
        print_info("Ticket might not be auto-assigned. Check agent availability settings.")

    sleep(1)

    test_agent_get_messages(token, chat_id)
    sleep(1)

    test_agent_send_reply(token, chat_id)
    sleep(1)

    test_agent_get_status(token)
    sleep(1)

    test_get_pending_tickets(token)
    sleep(1)

    # Uncomment to test resolve
    # test_resolve_ticket(token, chat_id)

    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}✓ Complete Flow Test Finished!{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}")

    print(f"\n{Colors.YELLOW}Summary:{Colors.END}")
    print("1. Customer message received via webhook")
    print("2. Chat created in database")
    print("3. Chat mode changed to AGENT")
    print("4. Agent logged in and set status to ONLINE")
    print("5. Customer sent another message → Ticket auto-created")
    print("6. Ticket auto-assigned to available agent (FCFS)")
    print("7. Agent retrieved assigned chats")
    print("8. Agent read messages")
    print("9. Agent sent reply to customer via WhatsApp")
    print("10. Agent status and statistics retrieved")
    print("11. Queue status checked")

    print(f"\n{Colors.GREEN}Next steps:{Colors.END}")
    print("• Test with actual WhatsApp number")
    print("• Configure WHAPI webhook to point to your server")
    print("• Test with multiple agents")
    print("• Test different ticket priorities")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Test interrupted by user{Colors.END}")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
