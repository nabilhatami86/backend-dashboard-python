# Ticketing System — Implementation Detail

Detail teknis sistem tiket: dari mana tiket dibuat, bagaimana assignment bekerja, dan cara resolve.

---

## Komponen Utama

| File | Peran |
|------|-------|
| `app/whapi/webhook.py` | Buat tiket saat bot eskalasi |
| `app/services/queue_service.py` | Assign, claim, transfer, resolve tiket |
| `app/models/ticket.py` | Model Ticket + enum status/priority |
| `app/models/queue_assignment.py` | Riwayat assignment per tiket |
| `app/routes/tickets.py` | Endpoint API tiket |

---

## Pembuatan Tiket (webhook.py)

Tiket dibuat via `get_or_create_ticket()` di `webhook.py`, bukan lewat QueueService. Ini karena pembuatan tiket terjadi di dalam request webhook yang sudah punya DB session dan chat object.

```python
def get_or_create_ticket(db: Session, chat: Chat, priority: TicketPriority = TicketPriority.medium) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.chat_id == chat.id).first()

    if ticket:
        if ticket.status not in [TicketStatus.resolved, TicketStatus.closed]:
            return ticket  # Tiket aktif sudah ada, tidak buat baru

        # Tiket resolved/closed → reset untuk percakapan baru
        ticket.status = TicketStatus.pending
        ticket.priority = priority
        ticket.assigned_agent_id = None
        ticket.created_at = datetime.now()
        ticket.assigned_at = None
        ticket.first_response_at = None
        ticket.resolved_at = None
        chat.assigned_agent_id = None
        db.commit()
        return ticket

    # Buat tiket baru
    new_ticket = Ticket(
        chat_id=chat.id,
        status=TicketStatus.pending,
        priority=priority,
        created_at=datetime.now(),
    )
    db.add(new_ticket)
    db.commit()
    return new_ticket
```

Fungsi ini dipanggil dari tiga titik di webhook:
1. Saat bot escalate (reply berisi kata-kata eskalasi)
2. Saat bot tidak bisa jawab (reply = `None`)
3. Saat customer ketik `#human`

Setelah tiket dibuat, `chat.mode` di-set ke `paused` agar bot tidak balas pesan berikutnya.

---

## QueueService

`QueueService` di `queue_service.py` mengurus semua operasi post-creation: assign, claim, transfer, resolve.

### Auto-assign (FCFS)

```python
queue_service = QueueService(db)
success = queue_service.auto_assign_ticket(ticket.id)
```

Algoritma `find_best_agent_fcfs()`:
1. Filter agent: `status=online` dan `is_available=True`
2. Skip agent yang sudah full capacity (`active_tickets >= max_concurrent_tickets`)
3. Pilih agent dengan ticket aktif paling sedikit
4. Tiebreaker: `last_activity_at` paling lama (paling idle)

### Self-claim oleh Agent

```python
success = queue_service.agent_claim_ticket(ticket_id=5, agent_id=2)
```

- Cek `ticket.status == pending`
- Cek `agent_profile.can_accept_ticket` (is_available + online + belum full)
- Set `ticket.status = assigned`, `ticket.assigned_at = now`
- Set `chat.mode = agent`, `chat.assigned_agent_id = agent_id`
- Buat record `QueueAssignment` (type: `claimed`)

### Manual Assign oleh Admin

```python
success = queue_service.manual_assign_ticket(
    ticket_id=5, agent_id=3, assigned_by_id=admin_id, reason="Spesialisasi produk X"
)
```

- Deactivate assignment sebelumnya jika ada
- Set agent baru, buat record `QueueAssignment` (type: `manual`)

### Transfer Tiket

```python
success = queue_service.transfer_ticket(
    ticket_id=5, from_agent_id=2, to_agent_id=4, reason="Shift berganti"
)
```

- Verifikasi agent tujuan online dan available
- Deactivate assignment lama
- Buat record `QueueAssignment` (type: `transferred`)

### Resolve Tiket

```python
success = queue_service.resolve_ticket(ticket.id)
```

- Set `ticket.status = resolved`, isi `resolved_at`
- Set `chat.mode = closed`
- Deactivate semua `QueueAssignment` aktif
- Increment `agent_profile.total_tickets_resolved`

---

## QueueAssignment — Audit Trail

Setiap kali tiket pindah tangan, ada record di tabel `queue_assignments`:

| Field | Keterangan |
|-------|------------|
| `assignment_type` | `auto`, `manual`, `claimed`, `transferred` |
| `assigned_by_id` | Admin yang assign (kalau manual) |
| `is_active` | Hanya satu yang `True` per tiket |
| `reason` | Alasan assignment/transfer |

Berguna untuk audit trail siapa yang pernah handle tiket.

---

## Endpoints Tiket

Prefix `/api` ditambahkan Nginx, tidak ada di FastAPI.

| Method | Path | Keterangan |
|--------|------|------------|
| `GET` | `/tickets/queue` | Tiket pending, sorted priority + FCFS |
| `GET` | `/tickets/my-tickets` | Tiket agent yang login |
| `GET` | `/tickets/all` | Semua tiket (admin only) |
| `POST` | `/tickets/{id}/claim` | Self-claim dari queue |
| `POST` | `/tickets/{id}/assign` | Admin assign ke agent |
| `POST` | `/tickets/{id}/transfer` | Transfer ke agent lain |
| `POST` | `/tickets/transfer-by-chat/{chat_id}` | Transfer via chat_id |
| `PATCH` | `/tickets/{id}/status` | Update status |
| `PATCH` | `/tickets/{id}/priority` | Update priority (admin only) |
| `POST` | `/tickets/{id}/resolve` | Resolve tiket |
| `GET` | `/tickets/stats/overview` | Statistik overview |
| `GET` | `/tickets/online-agents` | Agent online untuk dropdown transfer |

---

## Konfigurasi Priority Default

Tiket baru selalu dibuat dengan `priority=medium`. Untuk ubah per-kasus bisa override saat memanggil `get_or_create_ticket()`:

```python
# Di webhook.py — saat ini semua baru dengan medium
get_or_create_ticket(db, chat, priority=TicketPriority.medium)
```

Nilai yang tersedia: `low`, `medium`, `high`, `urgent`.

Admin bisa ubah priority setelah tiket dibuat via `PATCH /tickets/{id}/priority`.

---

## Monitoring via Logs

Log yang relevan di backend saat tiket dibuat/bergerak:

```
[TICKET CREATED] ticket_id=123 chat_id=45 priority=medium
[TICKET REOPEN] ticket_id=123 old_status=resolved
[TICKET REOPENED] ticket_id=123 chat_id=45 priority=medium
[ESCALATION] chat_id=45 is_group=False
[ESCALATION] ticket_id=123 status=pending
[HUMAN TRIGGER] chat_id=45 → escalating
[BOT SKIP] chat_id=45 mode=paused
[BOT RESET] chat_id=45 closed → bot
```

Query DB langsung:

```sql
-- Tiket yang menunggu di antrian
SELECT id, chat_id, status, priority, created_at
FROM tickets
WHERE status = 'pending'
ORDER BY priority ASC, created_at ASC;

-- Chat yang ada di queue (belum ada agent)
SELECT id, customer_name, mode, last_message_at
FROM chats
WHERE mode = 'paused' AND assigned_agent_id IS NULL
ORDER BY last_message_at ASC;
```
