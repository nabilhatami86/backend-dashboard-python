#!/usr/bin/env python3
"""
Test semua skenario agent warung madura secara otomatis
"""
import requests
import json
import time

WEBHOOK_URL = "http://localhost:8000/webhook/whapi"

# All scenarios
scenarios = [
    {
        "name": "Stock Habis",
        "from": "6281234567890@c.us",
        "from_name": "Warung Pak Budi",
        "message": "Min, stock indomie goreng habis. Kapan bisa restock?",
        "expected_keyword": "restock"
    },
    {
        "name": "Masalah Pembayaran",
        "from": "6282345678901@c.us",
        "from_name": "Warung Bu Siti",
        "message": "Admin, ada customer bayar tapi belum masuk ke sistem",
        "expected_keyword": "transaksi pembayaran"
    },
    {
        "name": "Sistem Error",
        "from": "6283456789012@c.us",
        "from_name": "Warung Mas Agus",
        "message": "Sistemnya error, gak bisa input pesanan baru",
        "expected_keyword": "teknis"
    },
    {
        "name": "Promo",
        "from": "6284567890123@c.us",
        "from_name": "Warung Mbak Rina",
        "message": "Min, ada promo bulan ini gak? Customer banyak yang nanya",
        "expected_keyword": "promo"
    },
    {
        "name": "Komplain Pengiriman",
        "from": "6285678901234@c.us",
        "from_name": "Warung Pak Joko",
        "message": "Pengiriman kemarin telat 3 jam, customer komplain",
        "expected_keyword": "logistik"
    },
]

def test_scenario(scenario):
    """Test single scenario"""
    payload = {
        "messages": [{
            "from": scenario["from"],
            "from_name": scenario["from_name"],
            "pushname": scenario["from_name"],
            "text": {
                "body": scenario["message"]
            },
            "timestamp": int(time.time())
        }]
    }

    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "chat_id": data.get("chat_id"),
                "bot_replied": data.get("bot_replied", False)
            }
        else:
            return {"success": False, "error": f"Status {response.status_code}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_chat_detail(chat_id, token):
    """Get chat detail from API"""
    try:
        response = requests.get(
            f"http://localhost:8000/chats/{chat_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def get_admin_token():
    """Get admin token"""
    try:
        response = requests.post(
            "http://localhost:8000/auth/login",
            json={"identifier": "admin", "password": "admin123"},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        return None
    except:
        return None


def main():
    print("=" * 70)
    print("TESTING ALL SCENARIOS - Agent Warung Madura")
    print("=" * 70)
    print()

    # Get admin token
    print("Getting admin token...")
    token = get_admin_token()
    if not token:
        print("❌ Failed to get admin token!")
        return

    print("✅ Token obtained\n")

    results = []
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] Testing: {scenario['name']}")
        print("-" * 70)
        print(f"Warung: {scenario['from_name']}")
        print(f"Pesan: {scenario['message'][:60]}...")

        result = test_scenario(scenario)

        if result["success"]:
            print(f"✅ Webhook SUCCESS - Chat ID: {result['chat_id']}")

            # Get chat detail
            if result["bot_replied"]:
                time.sleep(0.5)  # Wait for DB update
                chat_detail = get_chat_detail(result["chat_id"], token)

                if chat_detail:
                    name = chat_detail.get("name", "Unknown")
                    messages = chat_detail.get("messages", [])
                    last_bot_msg = None

                    # Find last bot message
                    for msg in reversed(messages):
                        if msg["sender"] == "agent":
                            last_bot_msg = msg["text"]
                            break

                    print(f"   Name saved: {name}")
                    if last_bot_msg:
                        print(f"   Bot reply: {last_bot_msg[:80]}...")

                        # Check if expected keyword in bot response
                        if scenario["expected_keyword"].lower() in last_bot_msg.lower():
                            print(f"   ✅ Keyword '{scenario['expected_keyword']}' found in response")
                            result["keyword_match"] = True
                        else:
                            print(f"   ⚠️  Keyword '{scenario['expected_keyword']}' NOT found")
                            result["keyword_match"] = False
                else:
                    print("   ⚠️  Could not fetch chat detail")
        else:
            print(f"❌ FAILED: {result.get('error')}")

        results.append({"scenario": scenario["name"], **result})

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    success_count = sum(1 for r in results if r.get("success"))
    bot_reply_count = sum(1 for r in results if r.get("bot_replied"))
    keyword_match_count = sum(1 for r in results if r.get("keyword_match"))

    print(f"\nTotal Scenarios: {len(scenarios)}")
    print(f"✅ Successful: {success_count}/{len(scenarios)}")
    print(f"🤖 Bot Replied: {bot_reply_count}/{len(scenarios)}")
    print(f"🎯 Keyword Match: {keyword_match_count}/{len(scenarios)}")

    print("\nDetailed Results:")
    for r in results:
        status = "✅" if r.get("success") else "❌"
        keyword = "🎯" if r.get("keyword_match") else "  "
        print(f"  {status} {keyword} {r['scenario']}")

    print("\n" + "=" * 70)
    print("Next Steps:")
    print("=" * 70)
    print("1. Open dashboard: http://localhost:3000/login")
    print("2. Login: admin / admin123")
    print("3. You should see 5 chats from different warungs")
    print("4. Each chat should have bot response matching keywords")
    print()


if __name__ == "__main__":
    main()
