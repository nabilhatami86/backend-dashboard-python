# backend-dashboard-python

API backend untuk dashboard customer service WhatsApp. Dibangun dengan FastAPI + PostgreSQL.

---

## Daftar Isi

1. [Apa ini?](#1-apa-ini)
2. [Struktur Folder](#2-struktur-folder)
3. [Cara Menjalankan](#3-cara-menjalankan)
4. [Environment Variables](#4-environment-variables)
5. [API Endpoints](#5-api-endpoints)
6. [Database Models](#6-database-models)
7. [Cara Kerja Internal](#7-cara-kerja-internal)
8. [Konfigurasi Bot AI](#8-konfigurasi-bot-ai)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Apa ini?

Backend ini bertugas:
- Menerima pesan masuk dari `wa-baileys-service` via webhook
- Menjalankan bot AI untuk menjawab pesan customer
- Mengelola chat, tiket, dan agent
- Menyediakan API untuk dashboard frontend
- Mengirim update real-time ke dashboard via WebSocket
- Meneruskan balasan agent ke WhatsApp via `wa-baileys-service`

```
wa-baileys-service ──► /webhook/baileys ──► Bot AI / Agent
                                                  │
                                                  ▼
                                           Dashboard Frontend
                                           (via WebSocket + REST API)
```

---

## 2. Struktur Folder

```
backend-dashboard-python/
├── app/
│   ├── main.py                    # FastAPI app, startup events, routes
│   ├── config/
│   │   ├── database.py            # Koneksi PostgreSQL (SQLAlchemy)
│   │   ├── deps.py                # Dependency injection (get_db)
│   │   ├── config.py              # Baca config DB
│   │   └── confiq_whapi.py        # Config WA provider (Baileys / WHAPI)
│   ├── models/                    # Tabel database (SQLAlchemy ORM)
│   │   ├── chat.py                # Tabel chats
│   │   ├── message.py             # Tabel messages
│   │   ├── ticket.py              # Tabel tickets
│   │   ├── user.py                # Tabel users (admin + agent)
│   │   ├── agent_profile.py       # Profil & status agent
│   │   ├── agent_metrics.py       # Metrik performa agent
│   │   ├── queue_assignment.py    # Antrian tiket
│   │   └── shortcut_message.py    # Pesan shortcut
│   ├── controller/                # Business logic
│   │   ├── chat_controller.py
│   │   ├── auth_controller.py
│   │   ├── users_controller.py
│   │   ├── admin_chat_controller.py
│   │   └── shortcut_controller.py
│   ├── services/
│   │   ├── bot_service.py         # Logika bot AI + state machine
│   │   ├── ws_manager.py          # Broadcast WebSocket
│   │   └── queue_service.py       # Manajemen antrian tiket
│   ├── routes/                    # Router FastAPI
│   │   ├── auth.py
│   │   ├── chat.py
│   │   ├── users.py
│   │   ├── tickets.py
│   │   ├── agent_chat.py
│   │   ├── admin_chat.py
│   │   ├── shortcuts.py
│   │   └── ws.py                  # WebSocket endpoint
│   ├── whapi/
│   │   ├── webhook.py             # Endpoint penerima pesan dari Baileys
│   │   └── client.py              # Kirim pesan ke WA via Baileys / WHAPI
│   └── schemas/                   # Pydantic schemas (request/response)
├── alembic/                       # Migrasi database
├── uploads/                       # File media yang diterima dari customer
├── .env
└── requirements.txt
```

---

## 3. Cara Menjalankan

### Install dependencies

```bash
python -m venv .venv

# Aktifkan virtual environment
source .venv/bin/activate      # Linux / Mac
.venv\Scripts\activate          # Windows

pip install -r requirements.txt
```

### Setup database

Pastikan PostgreSQL sudah berjalan, lalu buat database:

```sql
CREATE DATABASE dashboard_db;
```

Jalankan migrasi:

```bash
alembic upgrade head
```

### Buat file `.env`

Lihat bagian [Environment Variables](#4-environment-variables).

### Jalankan server

```bash
# Development (auto-reload)
uvicorn app.main:app --reload --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Server berjalan di `http://localhost:8000`.
Dokumentasi API otomatis tersedia di `http://localhost:8000/docs`.

### Jalankan dengan Docker

```bash
cd project-root
docker-compose up -d
```

---

## 4. Environment Variables

Buat file `.env` di root folder `backend-dashboard-python/`:

```env
# ── Database ──────────────────────────────────────
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dashboard_db
DB_USER=postgres
DB_PASSWORD=postgres123

# ── Auth (JWT) ────────────────────────────────────
SECRET_KEY=ganti-dengan-string-acak-yang-panjang
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60000

# ── WhatsApp Provider ─────────────────────────────
# Pilihan: "baileys" atau "whapi"
WA_PROVIDER=baileys

# Jika WA_PROVIDER=baileys
BAILEYS_SERVICE_URL=http://localhost:3000
BAILEYS_API_KEY=baileys-internal-2026

# Jika WA_PROVIDER=whapi (legacy)
WHAPI_BASE_URL=https://gate.whapi.cloud
WHAPI_TOKEN=token-dari-whapi

# ── Bot AI ────────────────────────────────────────
BOT_REPLY_API_URL=https://api-ai-kamu.com/chat
BOT_REPLY_API_KEY=api-key-kamu
BOT_REPLY_API_TIMEOUT_SECONDS=15

# ── Admin WA ──────────────────────────────────────
# Nomor WA admin (bisa kirim command khusus ke bot)
WHAPI_ADMINS=628111,628222
```

---

## 5. API Endpoints

### Auth
| Method | Path | Keterangan |
|--------|------|------------|
| `POST` | `/api/auth/login` | Login, dapat JWT token |
| `GET` | `/api/auth/me` | Info user yang sedang login |

### Chat (Admin)
| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/api/admin/chats` | List semua chat aktif |
| `GET` | `/api/admin/chats/{id}` | Detail chat + semua pesan |
| `POST` | `/api/admin/chats/{id}/messages` | Kirim pesan sebagai agent |
| `PATCH` | `/api/admin/chats/{id}` | Update mode / assign agent |
| `DELETE` | `/api/admin/chats/{id}` | Hapus chat |

### Chat (Agent)
| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/api/agent/chats` | List chat yang di-assign ke agent ini |
| `GET` | `/api/agent/chats/{id}` | Detail chat |
| `POST` | `/api/agent/chats/{id}/messages` | Kirim pesan |
| `POST` | `/api/agent/chats/{id}/read` | Tandai semua pesan sudah dibaca |

### Tiket
| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/api/tickets` | List tiket yang tersedia di antrian |
| `POST` | `/api/tickets/{id}/claim` | Agent ambil tiket |

### Users (Admin)
| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/api/users/agents` | List semua agent |
| `POST` | `/api/users/agents` | Buat agent baru |
| `PUT` | `/api/users/agents/{id}` | Edit agent |
| `DELETE` | `/api/users/agents/{id}` | Hapus agent |

### Shortcuts
| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/api/shortcuts` | List pesan shortcut milik agent |
| `POST` | `/api/shortcuts` | Buat shortcut baru |
| `DELETE` | `/api/shortcuts/{id}` | Hapus shortcut |

### Webhook (dari Baileys service)
| Method | Path | Keterangan |
|--------|------|------------|
| `POST` | `/webhook/baileys` | Terima pesan masuk dari WA |
| `POST` | `/webhook/typing` | Terima typing indicator dari WA |

### WebSocket
| Path | Keterangan |
|------|------------|
| `WS /ws` | Real-time update ke dashboard |

### Health
| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/` | Health check |
| `GET` | `/db-connect` | Cek koneksi database |

---

## 6. Database Models

### Chat (`chats`)

Satu baris = satu percakapan aktif dengan satu customer (atau satu participant di grup).

| Kolom | Keterangan |
|-------|------------|
| `customer_name` | Nama customer |
| `customer_phone` | Nomor HP (tanpa `@`) |
| `group_id` | JID grup jika dari grup (e.g. `120363xxx@g.us`) |
| `group_name` | Nama grup |
| `last_participant_jid` | JID terakhir yang kirim pesan di grup (untuk auto-mention saat agent balas) |
| `mode` | `bot` / `agent` / `paused` / `closed` |
| `assigned_agent_id` | FK ke tabel users (agent yang handle) |
| `unread_count` | Jumlah pesan belum dibaca |

**Mode lifecycle:**
```
bot ──(AI tidak bisa jawab)──► paused ──(agent claim)──► agent ──(tutup)──► closed
 ▲                                                                              │
 └──────────────────────(customer chat lagi setelah closed)────────────────────┘
```

### Message (`messages`)

| Kolom | Keterangan |
|-------|------------|
| `chat_id` | FK ke tabel chats |
| `text` | Isi pesan |
| `sender` | `customer` atau `agent` |
| `status` | `sent` atau `read` |
| `participant_phone` | Nomor pengirim di grup |
| `participant_name` | Nama pengirim di grup |
| `media_url` | Path file di server (`/uploads/...`) |
| `media_type` | `image` / `video` / `audio` / `document` |
| `media_filename` | Nama file (untuk dokumen) |

### Ticket (`tickets`)

Satu tiket per chat. Melacak siapa yang handle dan berapa lama.

| Status | Keterangan |
|--------|------------|
| `pending` | Menunggu diambil agent |
| `assigned` | Sudah ada agent, belum mulai |
| `in_progress` | Sedang dikerjakan |
| `resolved` | Selesai |

### AgentProfile (`agent_profiles`)

Profil tambahan untuk user dengan role `agent`.

| Kolom | Keterangan |
|-------|------------|
| `display_name` | Tag nama di akhir pesan (`~ NamaAgent`) |
| `status` | `online` / `offline` / `busy` / `break` |
| `is_available` | Apakah bisa terima tiket baru |
| `last_activity_at` | Timestamp heartbeat terakhir (untuk deteksi agent idle) |

---

## 7. Cara Kerja Internal

### Webhook Penerima Pesan (`whapi/webhook.py`)

```
POST /webhook/baileys
        │
        ▼
[1] Deteksi format (Baileys single-object atau WHAPI array)
        │
        ▼
[2] is_group? → wajib ada mention → tidak ada? SKIP
        │
        ▼
[3] Deduplication — cegah proses pesan yang sama dua kali
        │
        ▼
[4] get_or_create_chat()
    - Grup:    cari/buat berdasarkan (group_id + participant_phone)
    - Private: cari/buat berdasarkan (customer_phone)
        │
        ▼
[5] Simpan media ke uploads/ (jika ada)
        │
        ▼
[6] save_customer_message() → simpan ke DB
        │
        ▼
[7] WebSocket broadcast → dashboard update real-time
        │
        ▼
[8] mode = bot? → handle_bot() → generate AI reply
    mode = agent/paused? → SKIP (agent handle manual)
        │
        ▼
[9] Ada reply?
    ├── Ya → cek trigger eskalasi?
    │         ├── Iya → kirim ESCALATION_REPLY, mode → paused
    │         └── Tidak → kirim reply bot
    └── Tidak → eskalasi otomatis (mode → paused, kirim ESCALATION_REPLY)
        │
        ▼
[10] Kirim reply ke WA via client.py → wa-baileys-service
```

### Pesan Eskalasi

Saat bot tidak bisa menjawab, customer akan menerima:

> *"Baik kak, akan kami hubungi ke Customer Service kita, Sebentar ya"*

Dan chat masuk ke mode `paused` → tiket tersedia di antrian untuk diambil agent.

### Tag Agent di Pesan

Setiap pesan yang dikirim agent dari dashboard otomatis ditambah:
```
Halo kak, stok masih tersedia.
~ Nama Agent
```
Nama diambil dari `AgentProfile.display_name` atau nama user jika belum diset.

### Agent Status Auto-Reset

- **Saat startup:** semua agent di-reset ke `offline`
- **Background task (tiap 2 menit):** agent yang tidak kirim heartbeat > 3 menit → otomatis `offline` + broadcast WebSocket

---

## 8. Konfigurasi Bot AI

Bot memanggil external API untuk generate jawaban.

**Request yang dikirim ke AI API:**
```json
{
  "query": "pesan dari customer",
  "mode": "mpstore",
  "sessionId": "session-id-per-user"
}
```

`sessionId` disimpan per-user di memori agar percakapan tetap punya konteks.

**Format response yang diterima** (salah satu key ini valid):
```
reply / response / answer / message / text / result / data
```

**Jika AI tidak bisa jawab / timeout** → trigger eskalasi otomatis ke CS.

---

## 9. Troubleshooting

### Pesan masuk tidak tersimpan di DB

Cek log webhook:
```bash
grep "WEBHOOK" uvicorn.log
```
Pastikan Baileys service mengirim ke URL yang benar dan `INTERNAL_API_KEY` cocok dengan `BAILEYS_API_KEY` di `.env`.

### Bot tidak merespon

1. Cek `BOT_REPLY_API_URL` sudah diset di `.env`
2. Cek apakah mode chat saat ini `bot` (bukan `agent` atau `paused`)
3. Buka `http://localhost:8000/docs` → coba endpoint `/api/admin/chats/{id}` untuk cek mode

### Agent tidak bisa kirim pesan ke WA

Pastikan `BAILEYS_SERVICE_URL` dan `BAILEYS_API_KEY` sesuai dengan konfigurasi Baileys service yang berjalan.

### Database migration error

```bash
# Lihat versi migration saat ini
alembic current

# Lihat history
alembic history

# Rollback satu step
alembic downgrade -1

# Buat migration baru setelah ubah model
alembic revision --autogenerate -m "deskripsi perubahan"
alembic upgrade head
```

### Upload file gagal

```bash
mkdir -p uploads
chmod 755 uploads
```
