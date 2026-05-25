# Dashboard API — Dokumentasi

Backend dibangun dengan FastAPI + PostgreSQL. Berjalan di port `8000`.

Dokumentasi interaktif tersedia di `/docs` (Swagger UI) saat server berjalan.

---

## Auth

| Method | Endpoint | Keterangan |
|--------|----------|-----------|
| POST | `/api/auth/login` | Login, return JWT token |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/auth/me` | Ambil data user yang sedang login |

**Login request:**
```json
{ "username": "admin", "password": "password123" }
```
**Login response:**
```json
{ "access_token": "...", "token_type": "bearer", "user": { "id": 1, "name": "Admin", "role": "admin" } }
```

---

## Chat (Admin)

| Method | Endpoint | Keterangan |
|--------|----------|-----------|
| GET | `/api/chats` | Ambil semua chat |
| GET | `/api/chats/{id}` | Detail satu chat beserta messages |
| PATCH | `/api/chats/{id}/mode` | Ubah mode chat (bot/agent/paused/closed) |
| DELETE | `/api/chats/{id}` | Hapus chat |
| POST | `/api/chats/{id}/message` | Admin kirim pesan ke customer |

**Mode chat:**
- `bot` — dibalas otomatis oleh AI
- `agent` — dibalas oleh agent manusia
- `paused` — menunggu agent (masuk queue)
- `closed` — percakapan selesai

---

## Agent Chat

Semua endpoint di sini hanya bisa diakses oleh user dengan role `agent`.

| Method | Endpoint | Keterangan |
|--------|----------|-----------|
| GET | `/api/agent/chats/my-chats` | Ambil chat yang di-assign ke agent ini |
| GET | `/api/agent/chats/chat/{id}/messages` | Ambil messages dari satu chat |
| POST | `/api/agent/chats/send-message` | Kirim pesan ke customer via WhatsApp |
| POST | `/api/agent/chats/chat/{id}/mark-waiting` | Tandai ticket menunggu balasan customer |
| POST | `/api/agent/chats/chat/{id}/resolve` | Selesaikan / resolve ticket |
| GET | `/api/agent/chats/status` | Ambil status dan statistik agent |
| PATCH | `/api/agent/chats/status` | Update status availability agent |
| POST | `/api/agent/chats/heartbeat` | Heartbeat — dikirim frontend setiap ~90 detik |
| GET | `/api/agent/chats/daily-stats` | Statistik harian (handled & resolved hari ini) |

**Kirim pesan:**
```json
{
  "chat_id": 5,
  "text": "Halo kak, ada yang bisa kami bantu?",
  "media_url": null,
  "media_type": null,
  "media_filename": null
}
```

**Update status:**
```json
{ "is_available": true, "status": "online" }
```
Status yang valid: `online`, `offline`, `busy`, `break`

---

## Ticket Queue

| Method | Endpoint | Keterangan |
|--------|----------|-----------|
| GET | `/api/tickets/queue` | Ambil ticket yang belum diambil agent |
| POST | `/api/tickets/{id}/claim` | Agent claim / ambil ticket dari queue |
| GET | `/api/tickets/stats` | Statistik ticket (pending, in_progress, resolved, dll) |
| GET | `/api/tickets` | Semua ticket (admin) |

---

## Users / Agent Management (Admin)

| Method | Endpoint | Keterangan |
|--------|----------|-----------|
| GET | `/api/users/agents` | Daftar semua agent |
| POST | `/api/users/agents` | Tambah agent baru |
| PUT | `/api/users/agents/{id}` | Edit data agent |
| DELETE | `/api/users/agents/{id}` | Hapus agent |

**Tambah agent:**
```json
{
  "name": "Budi Santoso",
  "email": "budi@example.com",
  "username": "budi",
  "password": "rahasia123",
  "phone": "08123456789",
  "display_name": "Budi CS"
}
```

---

## Admin Chat (Internal)

Chat antara admin dan agent (bukan dengan customer).

| Method | Endpoint | Keterangan |
|--------|----------|-----------|
| GET | `/api/admin/chats/{agent_id}` | Ambil riwayat chat admin dengan agent tertentu |
| POST | `/api/admin/chats/{agent_id}/send` | Admin kirim pesan ke agent |

---

## WhatsApp Webhook

Menerima pesan masuk dari Baileys service.

| Method | Endpoint | Keterangan |
|--------|----------|-----------|
| POST | `/webhook/baileys` | Webhook utama — terima pesan dari WA |
| POST | `/webhook/typing` | Typing presence dari customer |

Webhook ini dipanggil oleh `wa-baileys-service`, bukan oleh frontend.

**Alur pesan masuk:**
1. Customer kirim pesan di WhatsApp
2. Baileys service forward ke `/webhook/baileys`
3. Backend simpan pesan ke DB dan broadcast ke dashboard via WebSocket
4. Jika mode=bot: bot AI balas otomatis
5. Jika bot escalate (atau customer ketik `#human`): ticket dibuat, mode → paused, masuk queue
6. Agent ambil ticket dari queue → mode → agent → agent balas manual

---

## WebSocket

| Endpoint | Keterangan |
|----------|-----------|
| `ws://host/ws/{chat_id}` | Subscribe ke update real-time satu chat |
| `ws://host/ws/global` | Subscribe ke update global (status agent, dll) |

**Event yang dikirim server:**
```json
{ "type": "new_message", "chat_id": 5 }
{ "type": "typing", "sender": "customer", "is_typing": true }
{ "type": "agent_status", "agent_id": 2, "status": "online", "is_available": true }
```

---

## Shortcuts

| Method | Endpoint | Keterangan |
|--------|----------|-----------|
| GET | `/api/shortcuts` | Ambil semua shortcut message |
| POST | `/api/shortcuts` | Tambah shortcut baru |
| PUT | `/api/shortcuts/{id}` | Edit shortcut |
| DELETE | `/api/shortcuts/{id}` | Hapus shortcut |

---

## Health Check

| Method | Endpoint | Keterangan |
|--------|----------|-----------|
| GET | `/` | Cek server jalan |
| GET | `/db-connect` | Cek koneksi database |

---

## Authentication

Semua endpoint (kecuali `/api/auth/login` dan health check) memerlukan header:

```
Authorization: Bearer <token>
```

Token didapat dari response `/api/auth/login`.
