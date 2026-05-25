# Controllers

Controller berisi logic bisnis yang dipanggil oleh routes. Routes cukup tangani HTTP (validasi, auth), logic ada di sini.

---

## auth_controller

**File:** `app/controller/auth_controller.py`

### `register_user(data, db)`
Buat user baru. Validasi:
- Email dan username harus unik
- Password minimal 6 karakter

```python
from app.controller.auth_controller import register_user

result = register_user({
    "name": "Budi",
    "email": "budi@example.com",
    "username": "budi",
    "password": "rahasia123",
    "role": "agent"
}, db)
```

### `login_user(data, db)`
Verifikasi kredensial dan return JWT token.

- Bisa login dengan `username` atau `email`
- Jika agent: auto-create `AgentProfile` jika belum ada, set status `online`
- Return: `{ access_token, token_type, user }`

```python
result = login_user({"username": "budi", "password": "rahasia123"}, db)
token = result["access_token"]
```

---

## chat_controller

**File:** `app/controller/chat_controller.py`

### `get_all_chats(db, user_id, user_role)`
Ambil semua chat aktif (non-closed). Agent hanya lihat chat yang di-assign ke mereka.

### `get_available_tickets(db)`
Ambil chat yang masuk queue: `mode=paused`, belum ada agent. Sorted by priority lalu `last_message_at` terlama.

### `claim_ticket(chat_id, agent_id, db)`
Agent ambil ticket dari queue. Pakai `WITH_FOR_UPDATE` lock untuk hindari race condition (dua agent claim ticket yang sama sekaligus).

- Cek apakah chat masih `paused` dan belum ada agent → kalau sudah diambil, raise 409
- Set `chat.mode = agent`, `chat.assigned_agent_id = agent_id`
- Update atau buat ticket, tutup QueueAssignment lama, buat yang baru

### `get_chat_detail(chat_id, db)`
Detail chat beserta semua messages. Juga ambil info agent yang assign dan riwayat transfer terakhir.

### `update_chat(chat_id, data, db)`
Update field chat:
- `mode` — ubah mode
- `assigned_agent_id` — assign/unassign agent
- `priority` — ubah prioritas

**Khusus:** Jika `mode=closed`:
1. Ticket di-resolve
2. Semua messages dihapus
3. Agent di-unassign

### `send_message(data, db)`
Simpan pesan ke DB. Jika pesan dari agent:
- Append signature agent (jika ada) ke teks yang dikirim ke WA
- Jika grup: tambah mention `@nomorhp` di awal
- Kirim ke WA via `send_text` atau `send_media`

### `mark_messages_as_read(chat_id, db)`
Set semua pesan customer → `read`, reset `unread_count` ke 0.

### `delete_chat(chat_id, db)`
Hapus chat dan semua messages (cascade).

### `update_message(message_id, new_text, db)`
Edit teks pesan. Hanya pesan dengan `sender=agent` yang bisa diedit.

### `update_tag_chat_agent(message_id, new_agent_name, db)`
Ganti atau tambah tag nama agent di akhir pesan. Format: `~ Nama`. Berguna saat agent ganti display name.

---

## users_controller

**File:** `app/controller/users_controller.py`

### `create_agent(data, db)`
Buat user dengan role `agent` + auto-create `AgentProfile`. Validasi email, username, dan password.

### `update_agent_full(user_id, data, db)`
Edit semua field agent: name, email, username, phone, password, display_name. Validasi uniqueness email dan username.

### `delete_agent(user_id, db)`
Hapus agent. Cascade delete `AgentProfile` dan data terkait.

### `update_agent_tag(user_id, display_name, db)`
Agent ganti display name sendiri (bukan admin yang ganti).

### `update_user_profile(user_id, data, db)`
Update profil umum user: name, email, phone.

### `get_all_agents(db)`
Ambil semua agent beserta info dari `AgentProfile` (status, is_available, display_name).

---

## admin_chat_controller

**File:** `app/controller/admin_chat_controller.py`

### `get_agent_admin_chat(agent_id, db)`
Ambil semua `AdminMessage` untuk agent tertentu. Return dalam format yang siap ditampilkan di chat window.

```python
result = get_agent_admin_chat(agent_id=3, db=db)
# result: { "id": 3, "mode": "manual", "messages": [...] }
```

### `send_admin_chat_message(agent_id, text, sender, sender_name, mode, db)`
Kirim pesan di internal chat. Jika `mode=bot`, auto-generate balasan berdasarkan keyword:

| Keyword | Balasan otomatis |
|---------|-----------------|
| `help`, `bantuan` | Panduan cara kerja sistem |
| `customer`, `pelanggan` | Info penanganan customer |
| `urgent`, `darurat` | Prosedur penanganan urgent |
| `?` | Daftar perintah |

---

## shortcut_controller

**File:** `app/controller/shortcut_controller.py`

### `search_shortcuts(keyword, db)`
Cari shortcut by key (`ILIKE %keyword%`). Dipakai untuk auto-suggest saat agent ketik `/` di chat.

```python
results = search_shortcuts("sala", db)
# Cari shortcut yang key-nya mengandung "sala"
```

### `create_shortcut(data, user_id, db)`
Buat shortcut baru. Key unik per user (bukan global). Raise 400 kalau key sudah ada.

### `duplicate_shortcut(shortcut_id, user_id, db)`
Salin shortcut milik agent lain ke koleksi sendiri. Berguna untuk berbagi template antar agent.

### `update_shortcut(shortcut_id, data, db)`
Edit key atau values shortcut. Validasi kalau key baru tidak bentrok dengan shortcut lain milik user yang sama.

---

## Catatan Umum

- Semua controller menerima `db: Session` sebagai parameter, bukan mengambil session sendiri.
- Error dikembalikan sebagai `HTTPException` dengan status code dan detail yang jelas.
- Controller tidak langsung kirim response — itu tugas routes. Controller cukup return data atau raise exception.

**Contoh pola route → controller:**

```python
# routes/users.py
@router.post("/agents")
def create_agent_endpoint(data: CreateAgentRequest, current_user = Depends(get_current_user), db = Depends(get_db)):
    if current_user.role != UserRole.admin:
        raise HTTPException(403, "Admin only")
    return create_agent(data.dict(), db)  # panggil controller

# controller/users_controller.py
def create_agent(data: dict, db: Session):
    # semua logic ada di sini
    ...
    return { "id": user.id, ... }
```
