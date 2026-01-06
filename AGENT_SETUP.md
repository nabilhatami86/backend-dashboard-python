# Agent Setup Documentation

## Overview
Sistem ini menggunakan **multi-agent dengan 1 nomor WhatsApp** yang terdaftar di WHAPI.

## WHAPI Configuration

**Channel:** CATWMN-PVGDR
**Phone Number:** +62 877 3162 4016
**API Token:** UlNfhibkobng15AcvcTMi7WqiWNJaVpq

## Agents Created

Total: **6 agents** (termasuk 1 agent demo lama)

### Agent Credentials

| Username | Password | Name | Email | Display Name |
|----------|----------|------|-------|--------------|
| agent | agent123 | Agent User | agent@example.com | - |
| agent1 | agent123 | Agent Satu | agent1@warungmadura.com | CS Warung Madura - Agent 1 |
| agent2 | agent123 | Agent Dua | agent2@warungmadura.com | CS Warung Madura - Agent 2 |
| agent3 | agent123 | Agent Tiga | agent3@warungmadura.com | CS Warung Madura - Agent 3 |
| agent4 | agent123 | Agent Empat | agent4@warungmadura.com | CS Warung Madura - Agent 4 |
| agent5 | agent123 | Agent Lima | agent5@warungmadura.com | CS Warung Madura - Agent 5 |

### Agent Profiles

Setiap agent memiliki:
- **Display Name:** Nama yang ditampilkan ke customer
- **Signature:** Tanda tangan di akhir pesan (contoh: "🙏 -Agent 1")
- **Expertise Tags:** Spesialisasi agent
- **Max Concurrent Tickets:** 5 tickets per agent
- **WhatsApp Number:** Semua menggunakan +62 877 3162 4016

### Agent Expertise

| Agent | Expertise Tags |
|-------|----------------|
| agent1 | general, order, menu |
| agent2 | general, billing, complaint |
| agent3 | general, delivery, tracking |
| agent4 | general, promotion, voucher |
| agent5 | general, technical, account |

## Configuration Files

### Environment Variables (.env)
```env
# WhatsApp API
WHAPI_BASE_URL=https://gate.whapi.cloud
WHAPI_TOKEN=UlNfhibkobng15AcvcTMi7WqiWNJaVpq
WHAPI_CHANNEL=CATWMN-PVGDR
WHAPI_PHONE=+6287731624016
```

### Settings (app/config/confiq_whapi.py)
Settings otomatis membaca dari `.env` file dengan default values untuk WHAPI_CHANNEL dan WHAPI_PHONE.

## Management Scripts

### 1. Create 5 Agents
```bash
python3 create_5_agents.py
```
Membuat 5 agent baru dengan konfigurasi yang sudah ditentukan.

**Options:**
- `--show` atau `-s`: Hanya menampilkan daftar agent tanpa membuat baru

### 2. Update Agent WhatsApp Numbers
```bash
python3 update_agent_whatsapp.py --yes
```
Update semua agent dengan nomor WhatsApp yang terdaftar di WHAPI.

**Options:**
- `--yes` atau `-y`: Auto-confirm tanpa prompt interaktif

### 3. Show Current Agents
```bash
python3 create_5_agents.py --show
```

## How Multi-Agent Works

1. **Single WhatsApp Number:** Semua agent menggunakan nomor WhatsApp yang sama (+62 877 3162 4016)
2. **Different Identities:** Setiap agent memiliki display name dan signature berbeda
3. **Message Format:**
   ```
   [Agent Response]

   🙏 -Agent 1
   ```
4. **Queue System:** Ticket akan di-assign ke agent berdasarkan availability dan capacity
5. **Agent Status:**
   - `online`: Ready to receive tickets
   - `offline`: Not available
   - `busy`: Working on tickets
   - `break`: On break

## Database Models

### User Model
- `id`: Primary key
- `name`: Agent full name
- `email`: Email address
- `username`: Login username
- `password`: Hashed password
- `phone`: WhatsApp number (same for all agents)
- `role`: UserRole.agent

### AgentProfile Model
- `user_id`: Foreign key to User
- `display_name`: Name shown to customers
- `signature`: Message signature
- `status`: AgentStatus (online/offline/busy/break)
- `is_available`: Boolean flag
- `max_concurrent_tickets`: Max capacity (default: 5)
- `expertise_tags`: Comma-separated specializations
- `priority_score`: Routing priority

## Usage in Code

### Get WHAPI Settings
```python
from app.config.confiq_whapi import settings

channel = settings.WHAPI_CHANNEL  # "CATWMN-PVGDR"
phone = settings.WHAPI_PHONE      # "+6287731624016"
token = settings.WHAPI_TOKEN
```

### Query Agents
```python
from app.models.user import User, UserRole
from app.models.agent_profile import AgentProfile

# Get all agents
agents = db.query(User).filter(User.role == UserRole.agent).all()

# Get agent profile
profile = db.query(AgentProfile).filter(
    AgentProfile.user_id == user_id
).first()

# Check if agent can accept ticket
if profile.can_accept_ticket:
    # Assign ticket to agent
    pass
```

## Notes

- Semua agent menggunakan password yang sama: `agent123` (untuk development)
- Dalam production, setiap agent harus memiliki password unik
- Status default: `offline` dan `is_available: False`
- Agent harus login dan set status ke `online` untuk menerima ticket
- Setiap agent dapat handle maksimal 5 tickets secara bersamaan
- WhatsApp API trial berlaku hingga 08.01.2026 (5 hari)
