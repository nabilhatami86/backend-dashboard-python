# Admin Chat Feature - Guide

## Overview
Admin Chat adalah fitur komunikasi internal antara Agent dan Admin. Berbeda dengan chat customer (via WhatsApp), admin chat disimpan di database PostgreSQL dan dapat diakses dari berbagai device/browser.

## Architecture

### Backend
- **Model**: `AdminMessage` di `app/models/admin_message.py`
- **Controller**: `admin_chat_controller.py`
- **Routes**: `/admin-chat/{agent_id}` endpoints
- **Database Table**: `admin_messages`

### Frontend
- **Agent Dashboard**: Tab "Admin Chat" untuk berkomunikasi dengan admin
- **API Client**: `lib/api.ts` - `getAdminChat()` dan `sendAdminMessage()`
- **Auto-refresh**: Messages otomatis ter-update setiap 5 detik

## Database Schema

```sql
CREATE TABLE admin_messages (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER NOT NULL,
    text VARCHAR NOT NULL,
    sender message_sender NOT NULL,  -- 'agent' atau 'admin'
    sender_name VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX ix_admin_messages_id ON admin_messages (id);
CREATE INDEX ix_admin_messages_agent_id ON admin_messages (agent_id);
```

## API Endpoints

### 1. Get Admin Chat Messages

**Request:**
```bash
GET /admin-chat/{agent_id}
```

**Response:**
```json
{
  "id": 2,
  "messages": [
    {
      "id": 1,
      "text": "Test message from admin",
      "sender": "admin",
      "sender_name": "Admin User",
      "time": "22:03",
      "status": "read"
    },
    {
      "id": 2,
      "text": "Test message from agent",
      "sender": "agent",
      "sender_name": "Agent User",
      "time": "22:05",
      "status": "read"
    }
  ]
}
```

### 2. Send Admin Chat Message

**Request:**
```bash
POST /admin-chat/{agent_id}/messages
Content-Type: application/json

{
  "text": "Hello from agent",
  "sender": "agent",
  "sender_name": "Agent User"
}
```

**Response:**
```json
{
  "id": 3,
  "text": "Hello from agent",
  "sender": "agent",
  "sender_name": "Agent User",
  "time": "22:10",
  "status": "sent"
}
```

## Testing

### Test via curl

**Get messages:**
```bash
curl http://localhost:8000/admin-chat/2
```

**Send message from agent:**
```bash
curl -X POST "http://localhost:8000/admin-chat/2/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Message from agent",
    "sender": "agent",
    "sender_name": "Agent User"
  }'
```

**Send message from admin:**
```bash
curl -X POST "http://localhost:8000/admin-chat/2/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Message from admin",
    "sender": "admin",
    "sender_name": "Admin Support"
  }'
```

### Test via Python

```python
from app.config.database import SessionLocal
from app.models.admin_message import AdminMessage, MessageSender

db = SessionLocal()

# Get all messages for agent ID 2
messages = db.query(AdminMessage).filter(
    AdminMessage.agent_id == 2
).order_by(AdminMessage.created_at.asc()).all()

for msg in messages:
    print(f"{msg.sender.value} ({msg.sender_name}): {msg.text}")

db.close()
```

## Frontend Usage

### Agent Dashboard

Agent dapat mengakses admin chat melalui:
1. Klik tab "Admin Chat" di dashboard agent
2. Ketik pesan di input box
3. Klik Send atau tekan Enter
4. Pesan akan tersimpan di database dan otomatis ter-refresh setiap 5 detik

### Code Example

```typescript
import { getAdminChat, sendAdminMessage } from "@/lib/api";

// Get admin chat messages
const adminChat = await getAdminChat(agentId);

// Send message from agent
await sendAdminMessage(
  agentId,           // Agent ID (e.g., 2)
  "Hello admin",     // Message text
  "Agent User",      // Sender name
  "agent"           // Sender type: "agent" or "admin"
);
```

## Migration History

1. **ee001a086c5c** - Add phone field to users table
2. **e016c0677dfa** - Add admin_messages table
3. **Manual** - Add 'admin' value to message_sender enum

To run migrations:
```bash
cd backend-dashboard-python/backend-dashboard-python.backup
python3 -m alembic upgrade head
```

## Notes

- **Auto-refresh**: Frontend melakukan polling setiap 5 detik untuk mendapatkan pesan baru
- **Real-time**: Pesan langsung tersimpan di database, tidak menggunakan localStorage
- **Multi-device**: Chat dapat diakses dari device/browser manapun
- **Agent ID**: Setiap agent memiliki chat room sendiri dengan admin berdasarkan agent_id
- **Message Sender**: Enum values: 'customer', 'agent', 'admin'

## Troubleshooting

### Messages tidak muncul
1. Cek apakah backend running: `http://localhost:8000/admin-chat/2`
2. Cek browser console untuk errors
3. Verify database connection: `curl http://localhost:8000/db-connect`

### Duplicate enum error saat migration
Jika ada error "type message_sender already exists", gunakan raw SQL:
```python
op.execute("""
    CREATE TABLE IF NOT EXISTS admin_messages (...)
""")
```

### Frontend tidak auto-refresh
Periksa useEffect di `dashboard-agent/page.tsx`:
```typescript
useEffect(() => {
  loadAdminChat();
  const interval = setInterval(loadAdminChat, 5000);
  return () => clearInterval(interval);
}, [user?.id]);
```
