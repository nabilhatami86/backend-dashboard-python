# Database Models

Semua model ada di `app/models/`. Pakai SQLAlchemy ORM.

---

## User

**Tabel:** `users`

| Field | Tipe | Keterangan |
|-------|------|-----------|
| `id` | Integer PK | |
| `name` | String | Nama lengkap |
| `email` | String unique | |
| `username` | String unique | Untuk login |
| `password` | String | Hashed (bcrypt) |
| `phone` | String nullable | |
| `role` | Enum | `admin` atau `agent` |
| `created_at` | DateTime | |

```python
from app.models.user import User, UserRole

# Cek role
if user.role == UserRole.admin: ...
if user.role == UserRole.agent: ...
```

---

## Chat

**Tabel:** `chats`

Satu chat = satu percakapan dengan satu customer (atau satu participant di grup).

| Field | Tipe | Keterangan |
|-------|------|-----------|
| `id` | Integer PK | |
| `customer_name` | String | |
| `customer_phone` | String (index) | Nomor WA |
| `group_id` | String nullable | JID grup WA (misal `12345@g.us`) |
| `group_name` | String nullable | Nama grup |
| `last_participant_jid` | String nullable | JID terakhir yang pesan di grup |
| `channel` | Enum | `whatsapp`, `telegram`, `email` |
| `mode` | Enum | `bot`, `agent`, `paused`, `closed` |
| `online` | Boolean | Customer sedang aktif |
| `unread_count` | Integer | Pesan belum dibaca agent |
| `assigned_agent_id` | Integer FK nullable | Agent yang handle chat ini |
| `priority` | Enum | `low`, `medium`, `high` |
| `last_message_at` | DateTime | |

**Relasi:**
- `assigned_agent` → User
- `messages` → List[Message]
- `ticket` → Ticket (one-to-one)

**Mode chat:**
- `bot` — dibalas AI otomatis
- `agent` — dibalas agent manusia
- `paused` — menunggu agent (ada di queue)
- `closed` — selesai

```python
from app.models.chat import Chat, ChatMode, ChatChannel

# Cari chat yang sedang di-handle agent
chats = db.query(Chat).filter(
    Chat.assigned_agent_id == agent_id,
    Chat.mode == ChatMode.agent
).all()
```

---

## Message

**Tabel:** `messages`

| Field | Tipe | Keterangan |
|-------|------|-----------|
| `id` | Integer PK | |
| `chat_id` | Integer FK | Relasi ke Chat |
| `text` | Text | Isi pesan |
| `sender` | Enum | `customer` atau `agent` |
| `status` | Enum | `sent` atau `read` |
| `agent_id` | Integer FK nullable | Diisi jika sender=agent |
| `media_url` | String nullable | URL file yang di-upload |
| `media_type` | String nullable | `image`, `video`, `document`, `audio` |
| `media_filename` | String nullable | Nama file asli |
| `participant_phone` | String nullable | Nomor pengirim di grup |
| `participant_name` | String nullable | Nama pengirim di grup |
| `created_at` | DateTime | |

---

## Ticket

**Tabel:** `tickets`

Satu chat punya tepat satu ticket (constraint unique di `chat_id`). Kalau ticket sudah resolved dan customer chat lagi, ticket yang sama di-reset (bukan dibuat baru).

| Field | Tipe | Keterangan |
|-------|------|-----------|
| `id` | Integer PK | |
| `chat_id` | Integer FK unique | Satu chat = satu ticket |
| `status` | Enum | Lihat di bawah |
| `priority` | Enum | `low`, `medium`, `high`, `urgent` |
| `assigned_agent_id` | Integer FK nullable | |
| `created_at` | DateTime | |
| `assigned_at` | DateTime nullable | Kapan di-assign ke agent |
| `first_response_at` | DateTime nullable | Kapan agent pertama kali balas |
| `resolved_at` | DateTime nullable | |
| `notes` | Text nullable | |
| `tags` | String nullable | |

**Status ticket:**
- `pending` — baru masuk, belum ada agent
- `assigned` — sudah di-assign tapi belum dibalas
- `in_progress` — agent sudah mulai balas
- `waiting_customer` — agent menunggu balasan customer
- `resolved` — selesai
- `closed` — ditutup paksa

**Properties (computed):**
```python
ticket.wait_time_seconds        # created_at → assigned_at
ticket.response_time_seconds    # created_at → first_response_at
ticket.resolution_time_seconds  # created_at → resolved_at
```

---

## AgentProfile

**Tabel:** `agent_profiles`

Data tambahan agent selain yang ada di tabel `users`. Auto-dibuat saat agent login pertama kali.

| Field | Tipe | Keterangan |
|-------|------|-----------|
| `id` | Integer PK | |
| `user_id` | Integer FK unique | Satu user = satu profile |
| `display_name` | String | Nama yang tampil di chat (bisa beda sama `name`) |
| `signature` | String nullable | Teks yang auto-append ke setiap pesan |
| `status` | Enum | `online`, `offline`, `busy`, `break` |
| `is_available` | Boolean | Bisa menerima ticket baru |
| `max_concurrent_tickets` | Integer | Default 5 |
| `last_activity_at` | DateTime nullable | Update tiap heartbeat |
| `total_tickets_handled` | Integer | Counter lifetime |
| `total_tickets_resolved` | Integer | Counter lifetime |

**Properties:**
```python
profile.can_accept_ticket   # is_available AND status==online AND not at_capacity
profile.is_at_capacity      # active_tickets >= max_concurrent_tickets
```

---

## QueueAssignment

**Tabel:** `queue_assignments`

Rekam jejak setiap kali ticket di-assign ke agent. Berguna untuk audit trail dan tracking transfer.

| Field | Tipe | Keterangan |
|-------|------|-----------|
| `id` | Integer PK | |
| `ticket_id` | Integer FK | |
| `agent_id` | Integer FK | Agent yang di-assign |
| `assignment_type` | Enum | `auto`, `manual`, `claimed`, `transferred` |
| `assigned_by_id` | Integer FK nullable | Admin yang assign (kalau manual) |
| `assigned_at` | DateTime | |
| `unassigned_at` | DateTime nullable | Diisi saat ticket pindah/selesai |
| `is_active` | Boolean | Hanya satu yang `True` per ticket |
| `reason` | String nullable | Alasan transfer/assignment |

---

## AdminMessage

**Tabel:** `admin_messages`

Pesan di internal chat antara admin dan agent (bukan chat dengan customer).

| Field | Tipe | Keterangan |
|-------|------|-----------|
| `id` | Integer PK | |
| `agent_id` | Integer | Agent yang diajak chat |
| `text` | String | Isi pesan |
| `sender` | Enum | `agent` atau `admin` |
| `sender_name` | String nullable | Nama pengirim |
| `mode` | Enum | `bot` (auto-reply) atau `manual` |
| `created_at` | DateTime | |

---

## ShortcutMessage

**Tabel:** `shortcut_messages`

Pesan cepat yang bisa dipanggil dengan `/key` di chat window.

| Field | Tipe | Keterangan |
|-------|------|-----------|
| `id` | Integer PK | |
| `key` | String | Kata kunci (unik per user) |
| `values` | Text | Isi pesan |
| `created_by` | Integer FK | User yang membuat |
| `created_at`, `updated_at` | DateTime | |

---

## AgentMetrics

**Tabel:** `agent_metrics`

Statistik harian per agent. Satu row per agent per hari.

| Field | Tipe | Keterangan |
|-------|------|-----------|
| `id` | Integer PK | |
| `agent_profile_id` | Integer FK | |
| `date` | Date | |
| `tickets_assigned` | Integer | |
| `tickets_resolved` | Integer | |
| `tickets_transferred` | Integer | |
| `avg_first_response_time` | Float | Detik |
| `avg_resolution_time` | Float | Detik |
| `total_messages_sent` | Integer | |
| `satisfaction_score` | Float nullable | |

---

## Diagram Relasi Singkat

```
User (1) ──── (1) AgentProfile ──── (n) AgentMetrics
  │
  └─── (n) Chat ──── (1) Ticket ──── (n) QueueAssignment
                │
                └─── (n) Message
                
User ──── (n) ShortcutMessage
```
