#!/bin/bash
echo "============================================================"
echo "Debug Webhook Setup"
echo "============================================================"
echo ""

echo "1. Checking Backend..."
if curl -s http://localhost:8000/ | grep -q "ok"; then
    echo "   ✅ Backend is running on port 8000"
else
    echo "   ❌ Backend NOT running!"
    echo "   Fix: cd backend-dashboard-python && python3 -m uvicorn app.main:app --reload"
fi
echo ""

echo "2. Checking ngrok..."
if ps aux | grep -q "[n]grok"; then
    echo "   ✅ ngrok is running"
    echo "   Check terminal for URL: https://xxx.ngrok-free.app"
else
    echo "   ❌ ngrok NOT running!"
    echo "   Fix: ngrok http 8000"
fi
echo ""

echo "3. Testing webhook endpoint locally..."
response=$(curl -s -X POST http://localhost:8000/webhook/whapi \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"from":"test@c.us","from_name":"Debug Test","text":{"body":"test from debug script"}}]}' 2>&1)

if echo "$response" | grep -q "ok"; then
    echo "   ✅ Webhook endpoint working!"
    echo "   Response: $response"
else
    echo "   ❌ Webhook endpoint error!"
    echo "   Response: $response"
fi
echo ""

echo "4. Checking database..."
chat_count=$(curl -s http://localhost:8000/chats/ | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
if [ -n "$chat_count" ]; then
    echo "   ✅ Database connected"
    echo "   Total chats: $chat_count"
else
    echo "   ❌ Cannot connect to database"
fi
echo ""

echo "============================================================"
echo "Next Steps to Fix Webhook:"
echo "============================================================"
echo ""
echo "1. Open ngrok Web Interface:"
echo "   http://127.0.0.1:4040"
echo ""
echo "2. Get your ngrok URL from terminal (look for):"
echo "   Forwarding    https://xxx.ngrok-free.app"
echo ""
echo "3. Bypass browser warning (IMPORTANT!):"
echo "   - Open: https://d79ed692219b.ngrok-free.app"
echo "   - Click 'Visit Site'"
echo ""
echo "4. Set webhook in WHAPI.cloud:"
echo "   - Login: https://whapi.cloud"
echo "   - Set webhook URL: https://d79ed692219b.ngrok-free.app/webhook/whapi"
echo ""
echo "5. Send WhatsApp message to bot number"
echo ""
echo "6. Monitor in ngrok Web UI (http://127.0.0.1:4040):"
echo "   - You should see: POST /webhook/whapi"
echo ""
echo "============================================================"
