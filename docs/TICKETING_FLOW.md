# Ticketing Flow

Alur lengkap dari pesan WhatsApp masuk sampai tiket selesai ditangani agent.

---

## Flow Utama

```
Customer kirim pesan WA
        │
        ▼
wa-baileys-service terima via Baileys
        │
        ▼
POST /webhook/baileys → backend
        │
        ├── Pesan grup tanpa mention? → SKIP
        │
        ├── Cek duplikat (MessageDedupCache) → sudah ada? SKIP
        │
        ▼
get_or_create_chat()
        │
        ▼
Simpan media ke /uploads/ (jika ada)
        │
        ▼
save_customer_message() → simpan ke DB
        │
        ▼
WebSocket broadcast → dashboard update
        │
        ▼
Cek chat.mode
        │
        ├── mode=closed atau (mode=paused dan belum ada agent)?
        │       → reset ke mode=bot (customer mulai chat baru)
        │
        ├── Customer ketik "#human"?
        │       → get_or_create_ticket() → mode=paused → kirim ESCALATION_REPLY → STOP
        │
        ├── mode=agent atau mode=paused?
        │       → BOT SKIP, tidak ada reply
        │
        └── mode=bot → proses ke bot AI
                │
                ▼
         handle_bot() → external AI API
                │
                ├── Ada reply & bukan eskalasi?
                │       → simpan reply, kirim ke WA
                │
                ├── Reply = eskalasi (kata kunci trigger)?
                │       → get_or_create_ticket()
                │         chat.mode = paused
                │         kirim ESCALATION_REPLY ke WA
                │
                └── Tidak ada reply?
                        → get_or_create_ticket()
                          chat.mode = paused
                          kirim ESCALATION_REPLY ke WA
```

---

## Lifecycle Chat Mode

```
bot ──(eskalasi / #human)──► paused ──(agent claim)──► agent ──(resolve)──► closed
 ▲                                                                               │
 └───────────────────────(customer chat baru setelah closed)────────────────────┘
```

- `bot` — dibalas AI otomatis
- `paused` — bot tidak bisa jawab, tiket masuk antrian, menunggu agent
- `agent` — agent sudah ambil tiket, handle manual
- `closed` — selesai

---

## Lifecycle Tiket

```
pending ──(agent claim / admin assign)──► assigned ──► in_progress
                                                           │
                                           ┌───────────────┤
                                           │               │
                                   waiting_customer    resolved ──► closed
```

| Status | Keterangan | Chat mode |
|--------|------------|-----------|
| `pending` | Tiket baru, belum ada agent | `paused` |
| `assigned` | Agent sudah claim, belum balas | `agent` |
| `in_progress` | Agent sedang aktif handle | `agent` |
| `waiting_customer` | Agent nunggu balasan customer | `agent` |
| `resolved` | Selesai | `closed` |
| `closed` | Ditutup paksa | `closed` |

---

## Cara Tiket Masuk Antrian

Tiket dibuat di fungsi `get_or_create_ticket()` di `webhook.py`, terpicu oleh tiga kondisi:

1. **Bot tidak bisa jawab** — `handle_bot()` return `None`
2. **Bot reply berisi kata eskalasi** — misal "silahkan hubungi kami melalui WhatsApp"
3. **Customer ketik `#human`** — trigger manual langsung ke CS

Setelah tiket dibuat, `chat.mode` di-set ke `paused`. Chat yang `mode=paused` dan belum ada `assigned_agent_id` muncul di antrian agent (`GET /chats/queue/available`).

---

## Cara Agent Claim Tiket

### Via dashboard agent queue (`/dashboard-agent-queue`)

Agent lihat daftar chat yang menunggu, klik tombol claim.

### Via API

```
POST /chats/{chat_id}/claim
```

atau via tickets:

```
POST /tickets/{ticket_id}/claim
```

Saat claim:
- `chat.mode` → `agent`
- `chat.assigned_agent_id` → ID agent
- `ticket.status` → `assigned`
- `ticket.assigned_at` → timestamp claim
- Record `QueueAssignment` dibuat (type: `claimed`)

---

## Tiket Reopen

Satu chat hanya punya satu tiket (constraint unique `chat_id`). Kalau customer chat lagi setelah tiket resolved/closed:

1. Webhook deteksi `chat.mode=closed` → reset ke `mode=bot`
2. Bot proses pesan baru
3. Jika bot eskalasi → `get_or_create_ticket()` reset tiket yang ada (status kembali ke `pending`, field timestamps di-clear)

---

## Queue Ordering

Antrian diurutkan: **priority tertinggi dulu**, lalu **paling lama menunggu (FCFS)**.

```
[1] URGENT — created 10:00   ← diambil duluan
[2] HIGH   — created 10:05
[3] MEDIUM — created 10:03
[4] MEDIUM — created 10:08
[5] LOW    — created 10:10
```
