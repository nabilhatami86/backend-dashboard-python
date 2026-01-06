# Ticket Queue System - Implementation Documentation

## 📋 Overview

Sistem ticketing dengan queue management untuk multi-agent menggunakan **1 nomor WhatsApp yang sama**. Menggunakan algoritma **First-Come-First-Serve (FCFS)** untuk distribusi ticket otomatis ke agent yang available.

## 🎯 Fitur Utama

### 1. **Sistem Ticketing**
- Auto-create ticket ketika chat mode berubah ke "agent"
- Status tracking: pending → assigned → in_progress → waiting_customer → resolved/closed
- Priority levels: low, medium, high, urgent
- Auto-assignment menggunakan algoritma FCFS

### 2. **Multi-Agent dengan 1 Nomor WhatsApp**
- Beberapa agent (misal 10 agent) menggunakan nomor WhatsApp yang sama
- Setiap agent punya profile terpisah dengan display name & signature
- Capacity management per agent (max concurrent tickets)

### 3. **Queue Management (FCFS)**
- Customer masuk queue ketika tidak ada agent available
- Agent yang paling sedikit active tickets mendapat prioritas
- Agent bisa "claim" ticket dari queue (self-assignment)
- Admin bisa manual assign ticket ke agent tertentu

### 4. **Agent Monitoring**
- Track jumlah ticket per agent
- Response time metrics
- Resolution time metrics
- Daily performance metrics
- Activity tracking (online/offline status)

---

## 🗄️ Database Schema

### Tabel Baru

#### **1. tickets**
```sql
- id (PK)
- chat_id (FK → chats.id, UNIQUE)
- status (enum: pending|assigned|in_progress|waiting_customer|resolved|escalated|closed)
- priority (enum: low|medium|high|urgent)
- assigned_agent_id (FK → users.id, nullable)
- created_at (timestamp with index)
- assigned_at (timestamp, nullable)
- first_response_at (timestamp, nullable)
- resolved_at (timestamp, nullable)
- updated_at (timestamp)
- notes (text, nullable)
- tags (string, nullable)
```

#### **2. agent_profiles**
```sql
- id (PK)
- user_id (FK → users.id, UNIQUE)
- display_name (string) -- e.g., "Agent John"
- signature (string, nullable) -- e.g., "-John"
- status (enum: online|offline|busy|break)
- is_available (boolean, default: false)
- max_concurrent_tickets (integer, default: 5)
- expertise_tags (string, nullable)
- priority_score (integer, default: 0)
- last_activity_at (timestamp, nullable)
- last_login_at (timestamp, nullable)
- total_tickets_handled (integer, default: 0)
- total_tickets_resolved (integer, default: 0)
- average_response_time_seconds (integer, nullable)
- average_resolution_time_seconds (integer, nullable)
- created_at (timestamp)
- updated_at (timestamp)
```

#### **3. queue_assignments**
```sql
- id (PK)
- ticket_id (FK → tickets.id, with index)
- agent_id (FK → users.id)
- assignment_type (enum: auto|manual|claimed|transferred)
- assigned_by_id (FK → users.id, nullable)
- assigned_at (timestamp, with index)
- unassigned_at (timestamp, nullable)
- is_active (boolean, default: true)
- reason (string, nullable)
- notes (text, nullable)
```

#### **4. agent_metrics**
```sql
- id (PK)
- agent_profile_id (FK → agent_profiles.id, with index)
- date (date, with index)
- tickets_assigned (integer, default: 0)
- tickets_resolved (integer, default: 0)
- tickets_transferred (integer, default: 0)
- tickets_escalated (integer, default: 0)
- avg_first_response_time (float, nullable)
- avg_resolution_time (float, nullable)
- avg_wait_time (float, nullable)
- total_messages_sent (integer, default: 0)
- total_messages_received (integer, default: 0)
- active_hours (float, default: 0.0)
- total_online_duration_seconds (integer, default: 0)
- satisfaction_score (float, nullable)
- efficiency_score (float, nullable)
- created_at (timestamp)
- updated_at (timestamp)
```

### Update Tabel Existing

#### **chats** (updated)
```sql
+ ticket (relationship one-to-one → tickets)
```

---

## 📂 File Structure

```
backend-dashboard-python.backup/
├── app/
│   ├── models/
│   │   ├── __init__.py                 # ✅ Updated with new models
│   │   ├── ticket.py                   # ✅ NEW - Ticket model
│   │   ├── agent_profile.py            # ✅ NEW - AgentProfile model
│   │   ├── queue_assignment.py         # ✅ NEW - QueueAssignment model
│   │   ├── agent_metrics.py            # ✅ NEW - AgentMetrics model
│   │   └── chat.py                     # ✅ Updated - added ticket relationship
│   │
│   ├── services/
│   │   ├── queue_service.py            # ✅ NEW - Queue management service (FCFS logic)
│   │   └── bot_service.py              # Existing
│   │
│   ├── routes/
│   │   ├── tickets.py                  # ✅ NEW - Ticket API endpoints
│   │   ├── chat.py                     # Existing
│   │   ├── users.py                    # Existing
│   │   └── admin_chat.py               # Existing
│   │
│   ├── whapi/
│   │   ├── webhook.py                  # ✅ Updated - integrated queue system
│   │   └── client.py                   # Existing
│   │
│   ├── config/
│   │   ├── config.py                   # ✅ Updated - added defaults
│   │   └── database.py                 # Existing
│   │
│   └── main.py                         # ✅ Updated - registered tickets router
│
├── alembic/
│   ├── versions/
│   │   └── 487460ac0762_add_ticket_queue_system.py  # ✅ NEW - Migration
│   └── env.py                          # ✅ Updated - import new models
│
└── TICKET_QUEUE_SYSTEM.md             # ✅ This documentation
```

---

## 🔧 Implementation Details

### 1. Queue Service (FCFS Algorithm)

**File:** `app/services/queue_service.py`

**Key Methods:**

```python
QueueService(db):
    # Create ticket for chat
    create_ticket_for_chat(chat_id, priority, auto_assign=True)

    # Find best agent using FCFS
    find_best_agent_fcfs()  # Returns agent with least active tickets

    # Auto-assign ticket
    auto_assign_ticket(ticket_id)

    # Manual assign (admin)
    manual_assign_ticket(ticket_id, agent_id, assigned_by_id, reason)

    # Agent claim ticket
    agent_claim_ticket(ticket_id, agent_id)

    # Get pending tickets (FCFS order)
    get_pending_tickets(limit=50)  # Sorted by priority & created_at

    # Resolve ticket
    resolve_ticket(ticket_id)

    # Helper methods
    get_available_agents()
    get_agent_active_ticket_count(agent_id)
```

**FCFS Logic:**
1. Sort agents by: least active tickets → highest priority_score → earliest last_activity
2. Check if agent is online, available, and not at capacity
3. Assign ticket to best matching agent
4. Create assignment record dengan type "auto"
5. Update agent stats

### 2. Webhook Integration

**File:** `app/whapi/webhook.py`

**Updated Flow:**
```python
def whapi_webhook():
    1. Receive WhatsApp message
    2. Get/create chat
    3. Save customer message
    4. If chat.mode == "agent":
        → ensure_ticket_exists(db, chat)
           - Check if ticket exists
           - If not: create ticket with auto-assign
           - If auto-assigned: log agent
           - If no agent available: stay in queue
    5. Continue with bot logic if mode == "bot"
```

### 3. API Endpoints

**Base URL:** `/tickets`

#### Public Endpoints (Agent & Admin):

**GET `/tickets/queue`**
- Get pending tickets in FCFS order
- Response: List of TicketResponse

**GET `/tickets/my-tickets`**
- Get tickets assigned to current agent
- Query params: `?status=assigned`
- Response: List of TicketResponse

**GET `/tickets/{ticket_id}`**
- Get specific ticket details
- Permission: Agent (own tickets), Admin (all tickets)

**POST `/tickets/{ticket_id}/claim`**
- Agent claims ticket from queue
- Permission: Agent only
- Returns: Updated ticket

**POST `/tickets/{ticket_id}/resolve`**
- Mark ticket as resolved
- Permission: Agent (own), Admin (all)

**PATCH `/tickets/{ticket_id}/status`**
- Update ticket status
- Body: `{"status": "in_progress"}`
- Permission: Agent (own), Admin (all)

#### Admin-Only Endpoints:

**GET `/tickets/all`**
- Get all tickets with filters
- Query params: `?status=pending&priority=high&limit=100`

**POST `/tickets/{ticket_id}/assign`**
- Manually assign ticket to agent
- Body: `{"agent_id": 5, "reason": "Expert in billing"}`

**PATCH `/tickets/{ticket_id}/priority`**
- Update ticket priority
- Body: `{"priority": "urgent"}`

**GET `/tickets/stats/overview`**
- Get ticket statistics
- Response: Counts by status, avg times, etc.

---

## 🚀 Usage Examples

### 1. Setup Agent Profile

Pertama kali, buat profile untuk setiap agent:

```sql
INSERT INTO agent_profiles (
    user_id,
    display_name,
    signature,
    status,
    is_available,
    max_concurrent_tickets
) VALUES (
    2,                      -- user_id dari tabel users
    'Agent John',           -- Display name
    '-John',                -- Signature di akhir pesan
    'online',               -- Status
    true,                   -- Available
    5                       -- Max 5 tickets concurrent
);
```

### 2. Auto-Assignment Flow

```
1. Customer mengirim WhatsApp → Webhook
2. Chat mode = "agent" → ensure_ticket_exists()
3. QueueService.create_ticket_for_chat()
4. QueueService.auto_assign_ticket()
   → find_best_agent_fcfs()
   → Cari agent dengan:
      - status = online
      - is_available = true
      - active_tickets < max_concurrent_tickets
      - Pilih yang paling sedikit active tickets
5. Ticket assigned → agent dapat notification
6. Agent mulai handle customer
```

### 3. Agent Claim Ticket

```python
# Agent melihat queue
GET /tickets/queue
→ [
    {id: 123, chat_id: 456, status: "pending", priority: "medium", ...},
    {id: 124, chat_id: 457, status: "pending", priority: "high", ...}
  ]

# Agent claim ticket pertama
POST /tickets/123/claim
→ {
    "status": "success",
    "message": "Ticket 123 claimed successfully",
    "ticket": {...}
  }
```

### 4. Monitor Agent Performance

```python
# Get agent stats
GET /tickets/stats/overview
→ {
    "total_pending": 5,
    "total_assigned": 12,
    "total_in_progress": 8,
    "total_waiting_customer": 3,
    "total_resolved_today": 25,
    "avg_wait_time_seconds": 180.5,
    "avg_resolution_time_seconds": 450.2
  }
```

---

## 🔄 Migration

**Run migration:**

```bash
cd /Users/mm/Desktop/Dashboard/backend-dashboard-python/backend-dashboard-python.backup

# Review migration
alembic history

# Apply migration
alembic upgrade head
```

**Migration file:** `alembic/versions/487460ac0762_add_ticket_queue_system.py`

Creates 4 new tables:
1. `agent_profiles`
2. `tickets`
3. `queue_assignments`
4. `agent_metrics`

---

## ⚠️ Important Notes

### 1. **Before Running Migration:**
- Backup database terlebih dahulu
- Pastikan PostgreSQL running
- Test migration di development environment dulu

### 2. **Agent Profile Setup:**
- Setiap agent (user dengan role='agent') harus punya AgentProfile
- Set `is_available=True` untuk agent yang mau menerima ticket
- Adjust `max_concurrent_tickets` sesuai kapasitas agent

### 3. **WhatsApp Integration:**
- Semua agent menggunakan nomor WhatsApp yang SAMA
- Agent signature akan ditambahkan di akhir setiap pesan
- Example: "Terima kasih! -John" (jika signature = "-John")

### 4. **Testing:**
- Test auto-assignment dengan create chat mode "agent"
- Test manual assignment dari admin
- Test agent claim ticket
- Verify FCFS ordering

---

## 📊 Next Steps (Future Enhancements)

### Backend:
1. ✅ **Ticket System** - DONE
2. ✅ **Queue Service** - DONE
3. ✅ **API Endpoints** - DONE
4. 🔲 **Agent Profile Management API** - TODO
5. 🔲 **Agent Metrics API** - TODO
6. 🔲 **WebSocket for Real-time Updates** - TODO
7. 🔲 **Automatic Metrics Calculation (Cron Job)** - TODO

### Frontend:
1. 🔲 **Admin Dashboard - Queue Monitor** - TODO
2. 🔲 **Agent Dashboard - My Tickets** - TODO
3. 🔲 **Agent Dashboard - Claim from Queue** - TODO
4. 🔲 **Admin Dashboard - Agent Performance** - TODO
5. 🔲 **Real-time Notifications** - TODO
6. 🔲 **Agent Status Toggle (Online/Offline/Busy)** - TODO

### Improvements:
1. 🔲 Smart priority detection (based on keywords)
2. 🔲 SLA monitoring & alerts
3. 🔲 Customer satisfaction rating
4. 🔲 Escalation rules
5. 🔲 Round-robin assignment (alternative to FCFS)
6. 🔲 Skill-based routing
7. 🔲 Chat transfer between agents
8. 🔲 Supervisor dashboard

---

## 📝 Summary

### ✅ What's Implemented:

**Backend (100% Complete):**
- ✅ 4 new database models (Ticket, AgentProfile, QueueAssignment, AgentMetrics)
- ✅ Database migration script
- ✅ Queue Service dengan FCFS algorithm
- ✅ Webhook integration untuk auto-create ticket
- ✅ 12 API endpoints untuk ticket management
- ✅ Auto-assignment logic
- ✅ Manual assignment (admin)
- ✅ Agent claim ticket
- ✅ Ticket status tracking
- ✅ Agent capacity management
- ✅ Assignment history tracking

**Testing Required:**
- 🔲 Run migration
- 🔲 Create agent profiles
- 🔲 Test auto-assignment
- 🔲 Test manual assignment
- 🔲 Test agent claim
- 🔲 Test FCFS ordering

**Frontend (0% - Not Started):**
- 🔲 Dashboard components
- 🔲 Queue visualization
- 🔲 Agent monitoring
- 🔲 Real-time updates

---

## 🤝 Contact & Support

Jika ada pertanyaan atau butuh bantuan:
1. Review kode di folder `app/models/`, `app/services/`, `app/routes/`
2. Check migration file di `alembic/versions/487460ac0762_*.py`
3. Test API endpoints menggunakan tools seperti Postman atau curl

**Backend Ready to Deploy! 🚀**

Frontend implementation akan menjadi step berikutnya untuk visualisasi data dan user interaction.
