# Services

Service adalah kelas/fungsi yang berisi logic yang sifatnya reusable dan bisa dipanggil dari mana saja (route, controller, background task).

---

## QueueService

**File:** `app/services/queue_service.py`

Semua logic yang berhubungan dengan antrian ticket: assignment, claim, transfer, resolve.

### Cara Pakai

```python
from app.services.queue_service import QueueService

# Di dalam endpoint / controller
queue_service = QueueService(db)
```

### Method

---

#### `find_best_agent_fcfs()`
Cari agent terbaik berdasarkan FCFS (First Come First Served). Pilih agent yang:
- Status `online` dan `is_available = True`
- Belum mencapai kapasitas maksimum ticket
- Jumlah ticket aktif paling sedikit (prioritas utama)
- Paling lama tidak aktif (prioritas kedua — bagi yang jumlah ticketnya sama)

```python
agent = queue_service.find_best_agent_fcfs()
if agent:
    print(f"Best agent: {agent.name}")
```

---

#### `auto_assign_ticket(ticket_id)`
Auto-assign ticket ke agent terbaik (pakai `find_best_agent_fcfs`). Buat record `QueueAssignment` dengan tipe `auto`.

```python
success = queue_service.auto_assign_ticket(ticket.id)
```

Return `True` kalau berhasil, `False` kalau tidak ada agent tersedia.

---

#### `agent_claim_ticket(ticket_id, agent_id)`
Agent ambil ticket sendiri dari queue. Cek dulu apakah agent masih punya kapasitas.

```python
success = queue_service.agent_claim_ticket(ticket_id=5, agent_id=2)
if not success:
    raise HTTPException(400, "Tidak bisa claim, kapasitas penuh")
```

Return `True` kalau berhasil, `False` kalau gagal (kapasitas penuh atau ticket sudah diambil).

---

#### `manual_assign_ticket(ticket_id, agent_id, assigned_by_id, reason=None)`
Admin assign ticket ke agent tertentu. Deactivate assignment sebelumnya, buat yang baru.

```python
success = queue_service.manual_assign_ticket(
    ticket_id=5,
    agent_id=3,
    assigned_by_id=admin_user.id,
    reason="Spesialis produk X"
)
```

---

#### `transfer_ticket(ticket_id, from_agent_id, to_agent_id, reason=None)`
Transfer ticket dari satu agent ke agent lain. Deactivate assignment lama, buat yang baru dengan tipe `transferred`.

```python
success = queue_service.transfer_ticket(
    ticket_id=5,
    from_agent_id=2,
    to_agent_id=4,
    reason="Shift berganti"
)
```

---

#### `resolve_ticket(ticket_id)`
Selesaikan ticket:
1. Set `ticket.status = resolved` dan isi `resolved_at`
2. Set `chat.mode = closed`
3. Deactivate semua `QueueAssignment` aktif
4. Increment `total_tickets_resolved` di `AgentProfile`

```python
success = queue_service.resolve_ticket(ticket.id)
```

---

#### `get_pending_tickets(limit=50)`
Ambil ticket dengan status `pending`, sorted by priority (high dulu) lalu `created_at` (yang lama dulu).

```python
tickets = queue_service.get_pending_tickets(limit=20)
```

---

#### `get_agent_active_ticket_count(agent_id)`
Hitung ticket aktif agent (status: `assigned`, `in_progress`, atau `waiting_customer`).

```python
count = queue_service.get_agent_active_ticket_count(agent_id=2)
```

---

#### `create_ticket_for_chat(chat_id, priority=medium, auto_assign=True)`
Buat ticket untuk chat. Kalau `auto_assign=True`, langsung coba auto-assign ke agent.

```python
ticket = queue_service.create_ticket_for_chat(
    chat_id=5,
    priority=TicketPriority.high,
    auto_assign=True
)
```

---

## ConnectionManager (WebSocket)

**File:** `app/services/ws_manager.py`

Kelola semua koneksi WebSocket dari dashboard client.

```python
from app.services.ws_manager import manager as ws_manager
```

Ada dua jenis channel:
- **Per-chat** — untuk typing indicator dan notifikasi pesan baru
- **Global** — untuk update status agent

### Method

---

#### `connect(ws, chat_id)` & `disconnect(ws, chat_id)`
Kelola koneksi WebSocket per chat.

```python
@router.websocket("/ws/{chat_id}")
async def websocket_endpoint(ws: WebSocket, chat_id: int):
    await ws_manager.connect(ws, chat_id)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_manager.disconnect(ws, chat_id)
```

---

#### `broadcast(chat_id, data)`
Kirim JSON ke semua client yang subscribe ke chat tertentu.

```python
# Notifikasi ada pesan baru
await ws_manager.broadcast(chat.id, {
    "type": "new_message",
    "chat_id": chat.id,
})

# Typing indicator
await ws_manager.broadcast(chat.id, {
    "type": "typing",
    "sender": "customer",
    "is_typing": True,
})
```

---

#### `connect_global(ws)` & `disconnect_global(ws)`
Kelola koneksi WebSocket global (tidak terikat ke chat tertentu).

---

#### `broadcast_global(data)`
Kirim ke semua client di channel global. Dipakai untuk broadcast status agent.

```python
await ws_manager.broadcast_global({
    "type": "agent_status",
    "agent_id": agent.id,
    "name": agent.name,
    "status": "online",
    "is_available": True,
})
```

---

## bot_service

**File:** `app/services/bot_service.py`

Logic pemrosesan pesan oleh bot AI. Entry point utama adalah fungsi `handle_bot`.

### `handle_bot(user, message)`

Dipanggil dari webhook setiap ada pesan masuk saat `chat.mode == "bot"`.

```python
from app.services.bot_service import handle_bot

# Di webhook handler
reply = await asyncio.to_thread(handle_bot, phone_number, text)
```

**Return value:**
- `None` — bot tidak bisa jawab → eskalasi ke CS
- `str` — teks balasan bot
- `"__ADMIN_REPLY__|target|text"` — format khusus untuk admin command

**Alur di dalam `handle_bot`:**
1. Cek apakah ada admin command (`@assign`, `@unassign`, `@reply`)
2. Cek apakah ada human agent yang baru balas dalam 1 jam terakhir (kalau ya, bot diam)
3. Panggil external bot API (`BOT_REPLY_API_URL`) untuk generate balasan
4. Return balasan atau `None` jika tidak ada

### Bot Commands (dari nomor admin)

Admin bisa kirim pesan ke nomor WA bot untuk kontrol:

| Command | Contoh | Keterangan |
|---------|--------|-----------|
| `@assign` | `@assign 628xxx` | Assign chat ke agent |
| `@unassign` | `@unassign 628xxx` | Unassign agent dari chat |
| `@reply` | `@reply 628xxx Halo kak` | Admin kirim pesan ke customer tertentu |

Nomor admin dikonfigurasi via env var `WHAPI_ADMINS` (comma-separated).
