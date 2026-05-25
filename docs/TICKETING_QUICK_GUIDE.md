# Ticketing — Panduan Singkat

Ringkasan cara kerja sistem tiket untuk agent dan admin.

---

## Alur Singkat

```
Customer kirim pesan WA
        │
        ▼
Bot coba jawab otomatis
        │
        ├── Bot bisa jawab → balas, selesai
        │
        └── Bot tidak bisa / customer ketik #human
                │
                ▼
         Tiket dibuat (status=pending)
         Chat masuk antrian (mode=paused)
                │
                ▼
         Agent lihat antrian → ambil tiket (CLAIM)
                │
                ▼
         Agent handle percakapan manual
                │
                ▼
         Agent selesaikan (RESOLVE) → tiket closed
```

---

## Untuk Agent

### 1. Lihat tiket yang menunggu

```
GET /tickets/queue
GET /chats/queue/available
```

Atau buka halaman antrian di dashboard (`/dashboard-agent-queue`).

Urutan antrian: priority tertinggi dulu, lalu yang paling lama menunggu (FIFO).

### 2. Ambil tiket (claim)

```
POST /tickets/{ticket_id}/claim
POST /chats/{chat_id}/claim
```

Setelah claim: tiket jadi milik agent (`status=assigned`), chat bisa dibalas.

### 3. Balas customer

Kirim pesan via `POST /agent/chats/send-message`. Pesan diteruskan ke WhatsApp customer.

### 4. Selesaikan tiket

```
POST /agent/chats/chat/{chat_id}/resolve
POST /tickets/{ticket_id}/resolve
```

Chat masuk mode `closed`. Tiket `status=resolved`.

---

## Untuk Admin

### Lihat semua tiket

```
GET /tickets/all?status=pending&priority=high
```

Filter by status dan priority.

### Assign tiket ke agent tertentu

```
POST /tickets/{ticket_id}/assign
Body: { "agent_id": 3, "reason": "Spesialisasi produk X" }
```

### Transfer tiket ke agent lain

```
POST /tickets/{ticket_id}/transfer
Body: { "to_agent_id": 4, "reason": "Shift berganti" }
```

Agent tujuan harus dalam status online dan available.

### Statistik tiket

```
GET /tickets/stats/overview
```

---

## Status Tiket

| Status | Artinya |
|--------|---------|
| `pending` | Belum ada agent, ada di antrian |
| `assigned` | Sudah di-claim/assign, belum dibalas |
| `in_progress` | Agent sedang aktif handle |
| `waiting_customer` | Menunggu balasan customer |
| `resolved` | Selesai |
| `closed` | Ditutup paksa |

---

## Catatan Penting

- Satu chat = satu tiket. Kalau customer chat lagi setelah closed, tiket yang sama di-reset (bukan buat baru).
- Tiket hanya muncul di antrian kalau `chat.mode=paused` dan belum ada agent yang assign.
- Setelah agent claim, chat otomatis masuk mode `agent` — bot tidak akan balas lagi.
- Agent yang kapasitas tiketnya penuh (`max_concurrent_tickets`) tidak bisa claim tiket baru.
