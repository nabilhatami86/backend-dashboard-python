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

Dokumentasi detail ada di folder [`docs/`](./docs/):
- [`docs/models.md`](./docs/models.md) — semua tabel database
- [`docs/routes.md`](./docs/routes.md) — semua endpoint API
- [`docs/services.md`](./docs/services.md) — QueueService, WebSocket, bot_service
- [`docs/controllers.md`](./docs/controllers.md) — business logic tiap controller

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
│   │   ├── deps.py                # Dependency injection (get_db, get_current_user)
│   │   ├── config.py              # Baca config DB
│   │   └── confiq_whapi.py        # Config WA provider (Baileys / WHAPI)
│   ├── models/                    # Tabel database (SQLAlchemy ORM)
│   │   ├── chat.py
│   │   ├── message.py
│   │   ├── ticket.py
│   │   ├── user.py
│   │   ├── agent_profile.py
│   │   ├── agent_metrics.py
│   │   ├── queue_assignment.py
│   │   ├── admin_message.py
│   │   └── shortcut_message.py
│   ├── controller/                # Business logic
│   │   ├── auth_controller.py
│   │   ├── chat_controller.py
│   │   ├── users_controller.py
│   │   ├── admin_chat_controller.py
│   │   └── shortcut_controller.py
│   ├── services/
│   │   ├── bot_service.py         # Logika bot AI + state machine
│   │   ├── ws_manager.py          # Broadcast WebSocket
│   │   └── queue_service.py       # Manajemen antrian tiket (FCFS)
│   ├── routes/                    # Router FastAPI
│   │   ├── auth.py
│   │   ├── chat.py
│   │   ├── users.py
│   │   ├── tickets.py
│   │   ├── agent_chat.py
│   │   ├── admin_chat.py
│   │   ├── shortcuts.py
│   │   └── ws.py
│   ├── whapi/
│   │   ├── webhook.py             # Endpoint penerima pesan dari Baileys
│   │   └── client.py              # Kirim pesan ke WA via Baileys / WHAPI
│   └── schemas/                   # Pydantic schemas (request/response)
├── docs/                          # Dokumentasi detail
├── alembic/                       # Migrasi database
├── uploads/                       # File media dari customer
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
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dashboard_db
DB_USER=postgres
DB_PASSWORD=postgres123

# Auth (JWT)
SECRET_KEY=ganti-dengan-string-acak-yang-panjang
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60000

# WhatsApp Provider — pilih "baileys" atau "whapi"
WA_PROVIDER=baileys

# Jika WA_PROVIDER=baileys
BAILEYS_SERVICE_URL=http://localhost:3000
BAILEYS_API_KEY=baileys-internal-2026

# Jika WA_PROVIDER=whapi (legacy)
WHAPI_BASE_URL=https://gate.whapi.cloud
WHAPI_TOKEN=token-dari-whapi

# Bot AI
BOT_REPLY_API_URL=https://api-ai-kamu.com/chat
BOT_REPLY_API_KEY=api-key-kamu
BOT_REPLY_API_TIMEOUT_SECONDS=15

# Nomor WA admin — bisa kirim command khusus ke bot (comma-separated)
WHAPI_ADMINS=628111,628222
```

---

## 5. API Endpoints

Prefix `/api` ditambahkan oleh Nginx/reverse proxy, tidak ada di kode FastAPI.
Untuk detail lengkap tiap endpoint lihat [`docs/routes.md`](./docs/routes.md).

### Auth — `/auth`
| Method | Path | Keterangan |
|--------|------|------------|
| `POST` | `/auth/login` | Login, dapat JWT token |
| `POST` | `/auth/register` | Daftar user baru |
| `POST` | `/auth/logout` | Logout, set agent offline |

### Chat — `/chats`
| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/chats` | List semua chat aktif |
| `GET` | `/chats/{id}` | Detail chat + semua pesan |
| `POST` | `/chats` | Buat chat baru |
| `PATCH` | `/chats/{id}` | Update mode / assign agent / prioritas |
| `DELETE` | `/chats/{id}` | Hapus chat (admin only) |
| `POST` | `/chats/messages` | Kirim pesan |
| `POST` | `/chats/{id}/read` | Tandai pesan sudah dibaca |
| `PATCH` | `/chats/messages/{id}` | Edit pesan agent |
| `DELETE` | `/chats/messages/{id}` | Hapus pesan |
| `GET` | `/chats/queue/available` | Daftar chat di antrian (mode=paused) |
| `POST` | `/chats/{id}/claim` | Agent ambil chat dari antrian |
| `POST` | `/chats/upload` | Upload file media |

### Agent — `/agent/chats`
| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/agent/chats/my-chats` | Chat yang di-assign ke agent |
| `GET` | `/agent/chats/chat/{id}/messages` | Pesan dari satu chat (paginated) |
| `POST` | `/agent/chats/send-message` | Kirim pesan ke customer via WA |
| `PATCH` | `/agent/chats/status` | Update status online/availability |
| `POST` | `/agent/chats/heartbeat` | Heartbeat tiap ~90 detik |
| `GET` | `/agent/chats/status` | Status lengkap agent |
| `GET` | `/agent/chats/daily-stats` | Statistik hari ini |
| `POST` | `/agent/chats/chat/{id}/mark-waiting` | Tandai menunggu balasan customer |
| `POST` | `/agent/chats/chat/{id}/resolve` | Selesaikan tiket |

### Tiket — `/tickets`
| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/tickets/queue` | Tiket pending di antrian |
| `GET` | `/tickets/my-tickets` | Tiket agent yang login |
| `GET` | `/tickets/all` | Semua tiket (admin only) |
| `GET` | `/tickets/{id}` | Detail satu tiket |
| `POST` | `/tickets/{id}/claim` | Agent self-claim tiket |
| `POST` | `/tickets/{id}/assign` | Admin assign tiket ke agent |
| `POST` | `/tickets/{id}/transfer` | Transfer tiket ke agent lain |
| `POST` | `/tickets/transfer-by-chat/{chat_id}` | Transfer via chat_id |
| `PATCH` | `/tickets/{id}/status` | Update status tiket |
| `PATCH` | `/tickets/{id}/priority` | Ubah prioritas (admin only) |
| `POST` | `/tickets/{id}/resolve` | Resolve tiket |
| `GET` | `/tickets/stats/overview` | Statistik overview semua tiket |
| `GET` | `/tickets/online-agents` | Agent online untuk dropdown transfer |

### Users — `/users`
| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/users/agents` | Semua agent + status |
| `GET` | `/users/admins` | Semua admin |
| `GET` | `/users` | Semua user |
| `POST` | `/users/agents` | Buat agent baru (admin only) |
| `PUT` | `/users/agents/{id}` | Edit agent (admin only) |
| `DELETE` | `/users/agents/{id}` | Hapus agent (admin only) |
| `PATCH` | `/users/agents/me/tag` | Agent ganti display_name sendiri |
| `PATCH` | `/users/{id}` | Update profil (name, email, phone) |

### Admin Chat — `/admin-chat`
| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/admin-chat/{agent_id}` | Riwayat chat internal admin-agent |
| `POST` | `/admin-chat/{agent_id}/messages` | Kirim pesan ke agent |

### Shortcuts — `/shortcuts`
| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/shortcuts` | Semua shortcut |
| `GET` | `/shortcuts/search?q=...` | Cari shortcut (untuk auto-suggest `/`) |
| `GET` | `/shortcuts/{id}` | Detail shortcut |
| `POST` | `/shortcuts` | Buat shortcut baru |
| `PATCH` | `/shortcuts/{id}` | Edit shortcut |
| `POST` | `/shortcuts/{id}/duplicate` | Salin shortcut agent lain |
| `DELETE` | `/shortcuts/{id}` | Hapus shortcut |

### WebSocket — `/ws`
| Path | Keterangan |
|------|------------|
| `WS /ws/agents` | Update status agent (global) |
| `WS /ws/{chat_id}` | Notifikasi pesan baru + typing per chat |

### Webhook (dari Baileys service)
| Method | Path | Keterangan |
|--------|------|------------|
| `POST` | `/webhook/baileys` | Pesan masuk dari WA |
| `POST` | `/webhook/typing` | Typing indicator dari customer |

### Health
| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/` | Health check |
| `GET` | `/db-connect` | Cek koneksi database |

---

## 6. Database Models

Detail lengkap semua model ada di [`docs/models.md`](./docs/models.md).

Model utama:

| Model | Tabel | Keterangan |
|-------|-------|------------|
| `User` | `users` | Admin dan agent |
| `Chat` | `chats` | Percakapan dengan customer |
| `Message` | `messages` | Pesan dalam chat |
| `Ticket` | `tickets` | Satu per chat, tracking status penanganan |
| `AgentProfile` | `agent_profiles` | Status, display_name, kapasitas agent |
| `QueueAssignment` | `queue_assignments` | Riwayat assignment tiket |
| `AdminMessage` | `admin_messages` | Chat internal admin-agent |
| `ShortcutMessage` | `shortcut_messages` | Template pesan cepat |
| `AgentMetrics` | `agent_metrics` | Statistik harian per agent |

**Mode chat lifecycle:**
```
bot ──(AI tidak bisa jawab)──► paused ──(agent claim)──► agent ──(tutup)──► closed
 ▲                                                                              │
 └──────────────────────(customer chat lagi setelah closed)────────────────────┘
```

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

Chat masuk mode `paused` → tiket tersedia di antrian untuk diambil agent.

### Tag Agent di Pesan

Setiap pesan yang dikirim agent dari dashboard otomatis ditambah:
```
Halo kak, stok masih tersedia.
~ Nama Agent
```
Nama diambil dari `AgentProfile.display_name`.

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
3. Buka `http://localhost:8000/docs` → coba endpoint `/chats/{id}` untuk cek mode

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
