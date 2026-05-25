# Backend Dashboard — Dokumentasi

Backend dibangun dengan **FastAPI + PostgreSQL + SQLAlchemy**.

Server berjalan di port `8000`. Dokumentasi interaktif (Swagger) tersedia di `/docs`.

---

## Struktur Folder

```
app/
├── models/       # ORM model — struktur tabel database
├── routes/       # Endpoint API (router FastAPI)
├── controller/   # Logic bisnis yang dipanggil dari routes
├── services/     # Service reusable (queue, bot, websocket)
├── whapi/        # Webhook WhatsApp dan HTTP client ke Baileys
├── config/       # Database, deps (get_db, get_current_user), env
└── utils/        # Helper (hash password, JWT, dll)
```

## Daftar Dokumen

| File | Isi |
|------|-----|
| [models.md](./models.md) | Semua tabel database: field, relasi, enum |
| [routes.md](./routes.md) | Semua endpoint API: method, path, request, response |
| [services.md](./services.md) | QueueService, ConnectionManager (WebSocket), bot_service |
| [controllers.md](./controllers.md) | Logic di balik setiap endpoint |

## Alur Utama

```
WhatsApp customer kirim pesan
  → Baileys service forward ke POST /webhook/baileys
  → Pesan disimpan ke DB, broadcast ke dashboard via WS
  → Jika mode=bot: bot AI balas otomatis
  → Jika bot escalate atau customer ketik #human:
      → Ticket dibuat, mode → paused, masuk queue
  → Agent buka /dashboard-agent-queue
  → Agent claim ticket → mode → agent
  → Agent balas manual via POST /agent/chats/send-message
  → Agent resolve → ticket selesai
```

## Authentication

Semua endpoint (kecuali `/api/auth/login`) butuh header:
```
Authorization: Bearer <token>
```
Token didapat dari response `POST /auth/login`.

Role yang tersedia: `admin`, `agent`. Beberapa endpoint hanya bisa diakses salah satu role.

## Environment Variables

| Variable | Keterangan |
|----------|-----------|
| `DB_HOST` | Host PostgreSQL |
| `DB_PORT` | Port PostgreSQL (default 5432) |
| `DB_NAME` | Nama database |
| `DB_USER` | Username database |
| `DB_PASSWORD` | Password database |
| `SECRET_KEY` | Key untuk JWT signing |
| `WHAPI_TOKEN` | Token Baileys/WHAPI service |
| `WHAPI_URL` | Base URL Baileys service |
| `BOT_REPLY_API_URL` | URL API bot AI eksternal |
| `NODE_ENV` | `development` atau `production` |
