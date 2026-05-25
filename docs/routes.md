# API Routes

Semua endpoint yang tersedia. Prefix `/api` ditambahkan oleh reverse proxy (Nginx/frontend), tidak ada di kode FastAPI.

---

## Auth — `/auth`

### POST `/auth/login`
Login user.

**Request:**
```json
{ "username": "admin", "password": "password123" }
```
Bisa pakai `username` atau `email`.

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "name": "Admin",
    "email": "admin@example.com",
    "role": "admin"
  }
}
```

### POST `/auth/register`
Daftarkan user baru.

**Request:**
```json
{ "name": "Budi", "email": "budi@example.com", "username": "budi", "password": "rahasia123", "role": "agent" }
```

### POST `/auth/logout`
Logout. Set status agent → offline, broadcast ke dashboard.

---

## Chat — `/chats`

### GET `/chats`
Ambil semua chat (non-closed). Agent hanya lihat chat yang di-assign ke dia.

**Response:** Array of chat objects dengan info terakhir.

### GET `/chats/{chat_id}`
Detail satu chat beserta semua messages.

### POST `/chats`
Buat chat baru.

**Request:**
```json
{ "customer_name": "John", "customer_phone": "628123456789" }
```

### PATCH `/chats/{chat_id}`
Update chat — assign agent, ubah mode, ubah prioritas.

**Request (contoh ubah mode):**
```json
{ "mode": "agent", "assigned_agent_id": 3 }
```
**Request (ubah prioritas):**
```json
{ "priority": "high" }
```
Jika `mode` di-set ke `closed`: ticket otomatis di-resolve, messages dihapus, agent di-unassign.

### DELETE `/chats/{chat_id}`
Hapus chat dan semua messages-nya. Admin only.

### POST `/chats/messages`
Kirim pesan ke chat.

**Request:**
```json
{
  "chat_id": 5,
  "text": "Halo kak",
  "sender": "agent",
  "agent_id": 2,
  "media_url": null,
  "media_type": null,
  "media_filename": null
}
```

### POST `/chats/{chat_id}/read`
Tandai semua pesan sebagai sudah dibaca, reset `unread_count` ke 0.

### PATCH `/chats/messages/{message_id}`
Edit teks pesan (hanya pesan agent).

### DELETE `/chats/messages/{message_id}`
Hapus satu pesan.

### GET `/chats/queue/available`
Ambil daftar ticket yang ada di queue (mode=paused, belum ada agent). Dipakai di halaman queue agent.

**Response:** Array chat sorted by priority lalu `last_message_at` (yang paling lama menunggu duluan).

### POST `/chats/{chat_id}/claim`
Agent ambil ticket dari queue.

**Response:**
```json
{ "status": "success", "chat_id": 5, "agent_id": 2 }
```
Kalau ticket sudah diambil agent lain → 409 Conflict.

### POST `/chats/upload`
Upload file (gambar/dokumen). Return URL yang bisa disertakan di pesan.

**Form data:** `file` (multipart). Maks 10MB untuk gambar, 25MB untuk dokumen.

**Response:**
```json
{ "url": "/uploads/20240524_143022_abc12345.jpg", "filename": "foto.jpg", "size": 204800 }
```

---

## Agent Chat — `/agent/chats`

Endpoint khusus agent. Semua butuh token dengan role `agent`.

### GET `/agent/chats/my-chats`
Ambil semua chat yang di-assign ke agent yang login.

### GET `/agent/chats/chat/{chat_id}/messages`
Ambil messages dari satu chat. Support pagination.

**Query params:** `limit` (default 50), `offset` (default 0)

### POST `/agent/chats/send-message`
Agent kirim pesan ke customer via WhatsApp.

**Request:**
```json
{
  "chat_id": 5,
  "text": "Halo kak, ada yang bisa kami bantu?",
  "media_url": null,
  "media_type": null,
  "media_filename": null
}
```
Jika agent punya `signature` di profile, akan otomatis di-append ke pesan yang dikirim ke WA (tapi tidak disimpan ke DB).

### PATCH `/agent/chats/status`
Update status online/availability agent.

**Request:**
```json
{ "is_available": true, "status": "online" }
```
Status valid: `online`, `offline`, `busy`, `break`

Setelah update, broadcast ke semua client dashboard via WebSocket.

### POST `/agent/chats/heartbeat`
Heartbeat dari frontend — kirim tiap ~90 detik. Update `last_activity_at`. Agent yang tidak kirim heartbeat lebih dari 3 menit akan di-set offline oleh background task.

### GET `/agent/chats/status`
Ambil status lengkap agent (termasuk jumlah ticket aktif).

### GET `/agent/chats/daily-stats`
Statistik hari ini.

**Response:**
```json
{ "resolved_today": 5, "handled_today": 8, "date": "2024-05-24" }
```

### POST `/agent/chats/chat/{chat_id}/mark-waiting`
Tandai ticket sebagai menunggu balasan customer.

### POST `/agent/chats/chat/{chat_id}/resolve`
Selesaikan ticket. Mode chat otomatis di-set `closed`.

---

## Tickets — `/tickets`

### GET `/tickets/queue`
Ambil ticket pending yang bisa di-claim. Sorted by priority (high dulu), lalu waktu masuk (FIFO).

### GET `/tickets/my-tickets`
Ticket yang di-assign ke agent yang login.

**Query params:** `status` (opsional filter)

### GET `/tickets/all`
Semua ticket. Admin only.

**Query params:** `status`, `priority`, `limit` (default 50), `offset`

### GET `/tickets/{ticket_id}`
Detail satu ticket.

### POST `/tickets/{ticket_id}/claim`
Agent self-claim ticket dari queue. Cek kapasitas dulu (tidak bisa kalau sudah penuh).

### POST `/tickets/{ticket_id}/assign`
Admin assign ticket ke agent tertentu secara manual.

**Request:**
```json
{ "agent_id": 3, "reason": "Spesialisasi produk X" }
```

### POST `/tickets/{ticket_id}/transfer`
Transfer ticket ke agent lain.

**Request:**
```json
{ "to_agent_id": 4, "reason": "Shift berganti" }
```

### POST `/tickets/transfer-by-chat/{chat_id}`
Transfer ticket berdasarkan `chat_id` (lebih mudah dari sisi frontend).

### PATCH `/tickets/{ticket_id}/status`
Update status ticket.

**Request:**
```json
{ "status": "in_progress" }
```

### PATCH `/tickets/{ticket_id}/priority`
Ubah prioritas. Admin only.

**Request:**
```json
{ "priority": "high" }
```

### POST `/tickets/{ticket_id}/resolve`
Resolve ticket.

### GET `/tickets/stats/overview`
Statistik overview semua ticket.

**Response:**
```json
{
  "total_pending": 12,
  "total_in_progress": 5,
  "total_waiting_customer": 3,
  "total_assigned": 8,
  "total_resolved": 47,
  "avg_wait_time_seconds": 180,
  "avg_resolution_time_seconds": 3600
}
```

### GET `/tickets/online-agents`
Daftar agent yang online dan available. Dipakai untuk dropdown transfer.

---

## Users — `/users`

### GET `/users/agents`
Semua agent beserta status online dan display_name.

### GET `/users/admins`
Semua admin.

### GET `/users`
Semua user (admin + agent).

### POST `/users/agents`
Tambah agent baru. Admin only.

**Request:**
```json
{
  "name": "Siti Rahma",
  "email": "siti@example.com",
  "username": "siti_cs",
  "password": "rahasia123",
  "phone": "08123456789",
  "display_name": "Siti"
}
```

### PUT `/users/agents/{user_id}`
Edit semua field agent. Admin only. Password bisa dikosongkan (tidak berubah).

### DELETE `/users/agents/{user_id}`
Hapus agent. Admin only.

### PATCH `/users/agents/me/tag`
Agent ganti display_name miliknya sendiri.

**Request:**
```json
{ "display_name": "Budi CS" }
```

### PATCH `/users/{user_id}`
Update profil (name, email, phone).

---

## Admin Chat (Internal) — `/admin-chat`

### GET `/admin-chat/{agent_id}`
Ambil riwayat chat internal admin dengan agent tertentu.

### POST `/admin-chat/{agent_id}/messages`
Admin kirim pesan ke agent.

**Request:**
```json
{
  "text": "Hei, ada update dari manajemen",
  "sender": "admin",
  "sender_name": "Manajer",
  "mode": "manual"
}
```
Jika `mode=bot`, backend auto-generate balasan berdasarkan keyword.

---

## Shortcuts — `/shortcuts`

### GET `/shortcuts`
Semua shortcut message.

### GET `/shortcuts/search?q=halo`
Cari shortcut berdasarkan key. Dipakai untuk auto-suggest saat ketik `/` di chat.

### GET `/shortcuts/{shortcut_id}`
Detail satu shortcut.

### POST `/shortcuts`
Buat shortcut baru.

**Request:**
```json
{ "key": "salam", "values": "Halo kak, selamat datang! Ada yang bisa kami bantu?" }
```

### PATCH `/shortcuts/{shortcut_id}`
Edit shortcut.

### POST `/shortcuts/{shortcut_id}/duplicate`
Salin shortcut milik agent lain ke koleksi sendiri.

### DELETE `/shortcuts/{shortcut_id}`
Hapus shortcut.

---

## WebSocket — `/ws`

### `ws://host/ws/agents`
Global channel. Subscribe untuk menerima update status agent secara real-time.

**Event yang diterima:**
```json
{ "type": "agent_status", "agent_id": 2, "name": "Budi", "status": "online", "is_available": true }
```

### `ws://host/ws/{chat_id}`
Per-chat channel. Subscribe untuk menerima notifikasi pesan baru dan typing indicator.

**Event yang diterima:**
```json
{ "type": "new_message", "chat_id": 5 }
{ "type": "typing", "sender": "customer", "is_typing": true }
{ "type": "ticket_claimed", "chat_id": 5, "agent_id": 2 }
```

---

## Webhook WhatsApp — `/webhook`

Dipanggil oleh Baileys service, bukan frontend.

### POST `/webhook/baileys`
Terima pesan masuk dari WhatsApp.

### POST `/webhook/typing`
Terima typing presence event dari customer.

---

## Health Check

### GET `/`
```json
{ "status": "ok" }
```

### GET `/db-connect`
```json
{ "database": "postgresql", "status": "connected" }
```
