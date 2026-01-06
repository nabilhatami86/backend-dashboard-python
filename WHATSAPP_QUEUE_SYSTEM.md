# WhatsApp Chat Queue System Documentation

## 🎯 Overview

Sistem ini mengintegrasikan WhatsApp (via WHAPI) dengan sistem antrian customer support menggunakan multi-agent dengan 1 nomor WhatsApp.

## 📋 Flow Diagram

```
Customer (WhatsApp)
       ↓
   WHAPI Webhook
       ↓
  Webhook Handler
       ↓
  ┌────────────────┐
  │  Chat Created  │
  └────────────────┘
       ↓
  ┌────────────────────────────────┐
  │  Check Chat Mode               │
  ├────────────────────────────────┤
  │  • BOT: Auto-reply dari bot    │
  │  • AGENT: Create Ticket        │
  │  • PAUSED: No reply            │
  │  • CLOSED: No reply            │
  └────────────────────────────────┘
       ↓ (if AGENT mode)
  ┌────────────────┐
  │ Create Ticket  │
  │ (Priority: med)│
  └────────────────┘
       ↓
  ┌──────────────────────────┐
  │  Auto-Assign to Agent    │
  │  (FCFS Algorithm)        │
  └──────────────────────────┘
       ↓
  ┌────────────────────────────┐
  │  Agent receives ticket     │
  │  & can chat with customer  │
  └────────────────────────────┘
       ↓
  Agent sends reply via API
       ↓
  Message sent to WhatsApp
       ↓
  Customer receives message
```

## 🔄 Chat Modes

### 1. BOT Mode
- **Default mode** untuk chat baru
- Bot otomatis reply customer
- Tidak ada ticket dibuat
- Tidak ada agent assignment

### 2. AGENT Mode
- Chat ditangani oleh agent manusia
- Ticket otomatis dibuat
- Auto-assign ke agent yang available
- Pesan customer TIDAK dibalas otomatis
- Agent harus reply manual via API

### 3. PAUSED Mode
- Chat di-pause sementara
- Tidak ada bot reply
- Tidak ada ticket baru dibuat

### 4. CLOSED Mode
- Chat sudah selesai/closed
- Tidak ada response

## 🎫 Ticket Queue System

### Ticket Creation
Ticket otomatis dibuat ketika:
1. Chat mode di-set ke `AGENT`
2. Customer mengirim pesan pertama di mode AGENT
3. Webhook handler memanggil `ensure_ticket_exists()`

### Ticket Status
- **pending**: Baru masuk, belum di-assign
- **assigned**: Sudah di-assign ke agent
- **in_progress**: Agent sedang handle
- **waiting_customer**: Menunggu response customer
- **resolved**: Selesai ditangani
- **escalated**: Di-eskalasi ke supervisor
- **closed**: Ditutup

### Ticket Priority
- **urgent**: Priority tertinggi
- **high**: Priority tinggi
- **medium**: Priority normal (default)
- **low**: Priority rendah

### Auto-Assignment Algorithm (FCFS)

**First Come First Serve** dengan kriteria:
1. Agent harus **online** dan **available**
2. Agent belum mencapai **max concurrent tickets** (default: 5)
3. Pilih agent dengan:
   - Ticket aktif paling sedikit
   - Priority score tertinggi
   - Last activity paling lama (idle terlama)

## 👥 Agent Management

### Agent Profile Fields
```python
{
    "user_id": int,
    "display_name": str,           # Nama ditampilkan ke customer
    "signature": str,              # Signature di akhir pesan
    "status": "online|offline|busy|break",
    "is_available": bool,          # Bisa terima ticket baru?
    "max_concurrent_tickets": 5,   # Maks ticket bersamaan
    "expertise_tags": str,         # "billing,technical,sales"
    "priority_score": int,         # Untuk routing priority
}
```

### Agent Status
- **online**: Siap terima ticket
- **offline**: Tidak available
- **busy**: Sedang busy, tidak terima ticket baru
- **break**: Sedang break

### Agent Availability
Agent bisa terima ticket baru jika:
```python
is_available == True
AND status == "online"
AND active_tickets < max_concurrent_tickets
```

## 🔌 API Endpoints

### 1. WhatsApp Webhook (WHAPI → Backend)
```
POST /webhook/whapi
POST /webhook/whapi/messages
```

**Request Body** (dari WHAPI):
```json
{
  "messages": [
    {
      "from": "628123456789@c.us",
      "from_name": "John Doe",
      "text": {
        "body": "Halo, saya mau pesan"
      }
    }
  ]
}
```

**Response**:
```json
{
  "status": "ok",
  "mode": "agent",
  "chat_id": 123
}
```

### 2. Agent Chat Endpoints

#### Get My Chats (Agent's assigned chats)
```
GET /agent/chats/my-chats
Authorization: Bearer <agent_token>
```

**Response**:
```json
[
  {
    "id": 1,
    "customer_name": "John Doe",
    "customer_phone": "628123456789@c.us",
    "mode": "agent",
    "online": true,
    "unread_count": 3,
    "last_message_at": "2026-01-03T10:30:00",
    "ticket_id": 5,
    "ticket_status": "in_progress",
    "ticket_priority": "medium"
  }
]
```

#### Get Chat Messages
```
GET /agent/chats/chat/{chat_id}/messages?limit=50&offset=0
Authorization: Bearer <agent_token>
```

**Response**:
```json
[
  {
    "id": 1,
    "chat_id": 1,
    "text": "Halo, saya mau pesan",
    "sender": "customer",
    "status": "sent",
    "agent_id": null,
    "created_at": "2026-01-03T10:30:00"
  },
  {
    "id": 2,
    "chat_id": 1,
    "text": "Halo! Ada yang bisa kami bantu?",
    "sender": "agent",
    "status": "sent",
    "agent_id": 2,
    "created_at": "2026-01-03T10:31:00"
  }
]
```

#### Send Message to Customer
```
POST /agent/chats/send-message
Authorization: Bearer <agent_token>
Content-Type: application/json

{
  "chat_id": 1,
  "text": "Terima kasih! Kami akan proses pesanan Anda."
}
```

**Response**:
```json
{
  "status": "success",
  "message_id": 10,
  "chat_id": 1,
  "sent_to_whatsapp": true,
  "message": "Terima kasih! Kami akan proses pesanan Anda.\n\n🙏 -Agent 1"
}
```

**Note**: Pesan otomatis ditambahkan signature agent di akhir.

#### Update Agent Status
```
PATCH /agent/chats/status
Authorization: Bearer <agent_token>
Content-Type: application/json

{
  "is_available": true,
  "status": "online"
}
```

**Response**:
```json
{
  "status": "success",
  "agent_id": 2,
  "is_available": true,
  "status": "online",
  "can_accept_ticket": true
}
```

#### Get Agent Status
```
GET /agent/chats/status
Authorization: Bearer <agent_token>
```

**Response**:
```json
{
  "agent_id": 2,
  "name": "Agent Satu",
  "display_name": "CS Warung Madura - Agent 1",
  "status": "online",
  "is_available": true,
  "can_accept_ticket": true,
  "active_tickets": 2,
  "max_concurrent_tickets": 5,
  "total_tickets_handled": 15,
  "total_tickets_resolved": 12,
  "last_activity_at": "2026-01-03T10:30:00"
}
```

#### Mark Chat as Waiting for Customer
```
POST /agent/chats/chat/{chat_id}/mark-waiting
Authorization: Bearer <agent_token>
```

#### Resolve Chat
```
POST /agent/chats/chat/{chat_id}/resolve
Authorization: Bearer <agent_token>
```

**Response**:
```json
{
  "status": "success",
  "ticket_id": 5,
  "chat_id": 1,
  "resolved_at": "2026-01-03T11:00:00"
}
```

### 3. Ticket Management Endpoints

#### Get Pending Tickets (Queue)
```
GET /tickets/queue?limit=50
Authorization: Bearer <token>
```

#### Get My Tickets (Agent)
```
GET /tickets/my-tickets?status=in_progress
Authorization: Bearer <agent_token>
```

#### Claim Ticket (Self-assign)
```
POST /tickets/{ticket_id}/claim
Authorization: Bearer <agent_token>
```

#### Assign Ticket (Admin only)
```
POST /tickets/{ticket_id}/assign
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "agent_id": 2,
  "reason": "Expert in billing issues"
}
```

#### Update Ticket Status
```
PATCH /tickets/{ticket_id}/status
Authorization: Bearer <token>
Content-Type: application/json

{
  "status": "in_progress"
}
```

#### Get Ticket Statistics
```
GET /tickets/stats/overview
Authorization: Bearer <token>
```

## 🔐 Authentication

Semua endpoint (kecuali webhook) memerlukan JWT token:

```
Authorization: Bearer <jwt_token>
```

### Login to Get Token
```
POST /auth/login
Content-Type: application/json

{
  "username": "agent1",
  "password": "agent123"
}
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 2,
    "name": "Agent Satu",
    "email": "agent1@warungmadura.com",
    "role": "agent"
  }
}
```

## 📱 Complete Flow Example

### Scenario: Customer Kirim Pesan Pertama

**1. Customer kirim WhatsApp:**
```
WhatsApp: "Halo, saya mau tanya menu hari ini"
```

**2. WHAPI kirim webhook ke backend:**
```
POST /webhook/whapi/messages
{
  "messages": [{
    "from": "628123456789@c.us",
    "from_name": "Budi",
    "text": {"body": "Halo, saya mau tanya menu hari ini"}
  }]
}
```

**3. Backend process:**
- Create/get chat dari database
- Chat mode = `bot` (default)
- Save customer message
- Bot generate reply
- Send reply ke WhatsApp via WHAPI

**4. Customer dapat reply dari bot**

### Scenario: Escalate ke Agent

**Admin/System change chat mode ke AGENT:**
```
PATCH /chats/{chat_id}
{
  "mode": "agent"
}
```

**Next customer message:**
- Webhook receives message
- Check mode = `agent`
- **Create ticket** (auto)
- **Auto-assign to agent** (FCFS)
- **NO bot reply** (agent harus reply manual)

### Scenario: Agent Reply Customer

**1. Agent login:**
```
POST /auth/login
{"username": "agent1", "password": "agent123"}
```

**2. Agent set status online:**
```
PATCH /agent/chats/status
{"is_available": true, "status": "online"}
```

**3. Agent get assigned chats:**
```
GET /agent/chats/my-chats
```

**4. Agent get chat messages:**
```
GET /agent/chats/chat/1/messages
```

**5. Agent send reply:**
```
POST /agent/chats/send-message
{
  "chat_id": 1,
  "text": "Menu hari ini: Soto Madura, Nasi Bebek Goreng"
}
```

**6. Backend process:**
- Save message to DB
- Add agent signature
- Send to WhatsApp via WHAPI
- Update ticket status to `in_progress`
- Set `first_response_at` timestamp

**7. Customer receives:**
```
Menu hari ini: Soto Madura, Nasi Bebek Goreng

🙏 -Agent 1
```

### Scenario: Resolve Ticket

**Agent resolve chat:**
```
POST /agent/chats/chat/1/resolve
```

**Backend process:**
- Update ticket status to `resolved`
- Set `resolved_at` timestamp
- Change chat mode to `closed`
- Deactivate assignment
- Update agent stats

## 🎯 Key Features

### ✅ Multi-Agent Single Number
- Semua agent pakai 1 nomor WhatsApp: **+62 877 3162 4016**
- Setiap agent punya signature berbeda
- Customer tidak tahu ada berapa agent

### ✅ Automatic Queue Management
- Ticket otomatis dibuat di mode AGENT
- Auto-assign ke agent available
- FCFS algorithm
- Load balancing berdasarkan active tickets

### ✅ Agent Signature
- Setiap agent punya signature unik
- Otomatis ditambahkan di akhir pesan
- Contoh: "🙏 -Agent 1", "🙏 -Agent 2"

### ✅ Real-time Status
- Agent status: online/offline/busy/break
- Availability tracking
- Active ticket count
- Performance metrics

### ✅ Ticket Priority
- Support urgent, high, medium, low
- Priority-based queue ordering
- FCFS within same priority

### ✅ Complete Message History
- Semua pesan tersimpan di database
- Support pagination
- Filter by sender (customer/agent)

## 🔧 Configuration

### Environment Variables (.env)
```env
# WhatsApp API
WHAPI_BASE_URL=https://gate.whapi.cloud
WHAPI_TOKEN=UlNfhibkobng15AcvcTMi7WqiWNJaVpq
WHAPI_CHANNEL=CATWMN-PVGDR
WHAPI_PHONE=+6287731624016
```

### Agent Credentials
```
agent1 / agent123
agent2 / agent123
agent3 / agent123
agent4 / agent123
agent5 / agent123
```

### Admin Credentials
```
admin / admin123
```

## 📊 Database Models

### Chat
```python
id, customer_name, customer_phone, channel,
mode, online, unread_count, assigned_agent_id,
last_message_at, created_at
```

### Message
```python
id, chat_id, text, sender, status, agent_id,
created_at
```

### Ticket
```python
id, chat_id, status, priority, assigned_agent_id,
created_at, assigned_at, first_response_at,
resolved_at, notes, tags
```

### AgentProfile
```python
id, user_id, display_name, signature, status,
is_available, max_concurrent_tickets,
expertise_tags, priority_score,
total_tickets_handled, total_tickets_resolved
```

### QueueAssignment
```python
id, ticket_id, agent_id, assignment_type,
assigned_by_id, assigned_at, unassigned_at,
is_active, reason
```

## 🚀 Quick Start

### 1. Setup Database
```bash
# Database akan otomatis create tables saat startup
python3 -c "from app.config.database import engine, Base; Base.metadata.create_all(bind=engine)"
```

### 2. Create Agents
```bash
python3 create_5_agents.py
```

### 3. Run Server
```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Setup WHAPI Webhook
```bash
python3 setup_whapi_webhook.py
```

Point webhook ke:
```
https://your-domain.com/webhook/whapi/messages
```

### 5. Test Flow

**Test webhook:**
```bash
curl -X POST http://localhost:8000/webhook/whapi/messages \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{
      "from": "6281234567890@c.us",
      "from_name": "Test User",
      "text": {"body": "Hello"}
    }]
  }'
```

**Agent login:**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "agent1", "password": "agent123"}'
```

## 📝 Notes

- **Trial Period**: WHAPI trial berlaku sampai 08.01.2026
- **WhatsApp Requirement**: Buka WhatsApp mobile minimal 1x per 14 hari
- **Max Concurrent**: Default 5 tickets per agent (bisa diubah)
- **Signature**: Otomatis ditambahkan di setiap pesan agent
- **Bot Mode**: Default mode untuk chat baru, bisa diubah ke agent mode
- **Queue Algorithm**: FCFS (First Come First Serve) with load balancing

## 🐛 Troubleshooting

### Ticket tidak otomatis dibuat
- Pastikan chat mode = `agent`
- Check webhook berfungsi
- Check logs di backend

### Agent tidak terima ticket
- Pastikan agent status = `online`
- Pastikan `is_available = true`
- Check tidak melebihi `max_concurrent_tickets`
- Check agent profile exists

### Pesan tidak terkirim ke WhatsApp
- Check WHAPI token valid
- Check phone number format
- Check WHAPI webhook configured
- Check logs di backend

### Auto-assign tidak berfungsi
- Pastikan ada agent yang online dan available
- Check max concurrent tickets tidak penuh semua
- Check queue service logs
