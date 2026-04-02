"""
Debug script: cek kenapa ticket tidak muncul di queue.
Jalankan dari folder backend-dashboard-python:
  .venv\Scripts\python scripts/debug_ticket_queue.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config.database import SessionLocal
from app.models.chat import Chat, ChatMode
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.message import Message, MessageSender, MessageStatus
from datetime import datetime

db = SessionLocal()

SEP = "-" * 60

# ─── 1. CEK SEMUA CHAT ───────────────────────────────────────
print(SEP)
print("1. SEMUA CHAT DI DB")
print(SEP)
chats = db.query(Chat).all()
if not chats:
    print("  [KOSONG] Tidak ada chat sama sekali di DB")
else:
    for c in chats:
        print(f"  chat_id={c.id} | phone={c.customer_phone} | mode={c.mode.value} | assigned_agent_id={c.assigned_agent_id}")

# ─── 2. CEK SEMUA TICKET ─────────────────────────────────────
print()
print(SEP)
print("2. SEMUA TICKET DI DB")
print(SEP)
tickets = db.query(Ticket).all()
if not tickets:
    print("  [KOSONG] Tidak ada ticket sama sekali di DB")
else:
    for t in tickets:
        print(f"  ticket_id={t.id} | chat_id={t.chat_id} | status={t.status.value} | assigned_agent_id={t.assigned_agent_id}")

# ─── 3. QUERY PERSIS SEPERTI get_available_tickets ───────────
print()
print(SEP)
print("3. HASIL QUERY get_available_tickets (paused + ticket pending)")
print(SEP)
available = db.query(Chat).join(
    Ticket, Chat.id == Ticket.chat_id
).filter(
    Ticket.status == TicketStatus.pending,
    Ticket.assigned_agent_id == None,
    Chat.mode == ChatMode.paused,
).all()
if not available:
    print("  [KOSONG] Tidak ada ticket di queue")
    print()
    print("  Kemungkinan penyebab:")
    # Cek chat paused tanpa ticket
    paused_no_ticket = db.query(Chat).filter(Chat.mode == ChatMode.paused).all()
    for c in paused_no_ticket:
        t = db.query(Ticket).filter(Ticket.chat_id == c.id).first()
        if not t:
            print(f"  → chat_id={c.id} mode=paused TAPI TIDAK PUNYA TICKET")
        else:
            print(f"  → chat_id={c.id} mode=paused, ticket status={t.status.value} assigned_agent={t.assigned_agent_id}")

    # Cek ticket pending tanpa chat paused
    pending_tickets = db.query(Ticket).filter(Ticket.status == TicketStatus.pending).all()
    for t in pending_tickets:
        c = db.query(Chat).filter(Chat.id == t.chat_id).first()
        if c and c.mode != ChatMode.paused:
            print(f"  → ticket_id={t.id} status=pending TAPI chat mode={c.mode.value} (bukan paused)")
else:
    for c in available:
        print(f"  ✓ chat_id={c.id} | phone={c.customer_phone} | mode={c.mode.value}")

# ─── 4. SIMULATE ESCALATION FLOW ─────────────────────────────
print()
print(SEP)
print("4. SIMULATE ESCALATION → bikin chat test + ticket pending")
print(SEP)

TEST_PHONE = "test_debug_081247662703"
# Hapus data test lama jika ada
old_chat = db.query(Chat).filter(Chat.customer_phone == TEST_PHONE).first()
if old_chat:
    db.query(Ticket).filter(Ticket.chat_id == old_chat.id).delete()
    db.query(Message).filter(Message.chat_id == old_chat.id).delete()
    db.delete(old_chat)
    db.commit()
    print(f"  [CLEANUP] hapus chat test lama")

# Buat chat test (mode=bot, seperti chat baru dari WA)
test_chat = Chat(
    customer_name="Test Debug User",
    customer_phone=TEST_PHONE,
    channel="whatsapp",
    mode=ChatMode.bot,
    online=True,
    unread_count=1,
    last_message_at=datetime.now(),
)
db.add(test_chat)
db.commit()
db.refresh(test_chat)
print(f"  [OK] Chat dibuat: id={test_chat.id} mode={test_chat.mode.value}")

# Simulate escalation: buat ticket + ubah mode ke paused
test_ticket = Ticket(
    chat_id=test_chat.id,
    status=TicketStatus.pending,
    priority=TicketPriority.medium,
    created_at=datetime.now(),
)
db.add(test_ticket)
test_chat.mode = ChatMode.paused
db.commit()
db.refresh(test_ticket)
print(f"  [OK] Ticket dibuat: id={test_ticket.id} status={test_ticket.status.value}")
print(f"  [OK] Chat mode diubah ke: {test_chat.mode.value}")

# ─── 5. CEK QUERY LAGI SETELAH SIMULATE ──────────────────────
print()
print(SEP)
print("5. CEK QUEUE SETELAH SIMULATE")
print(SEP)
available2 = db.query(Chat).join(
    Ticket, Chat.id == Ticket.chat_id
).filter(
    Ticket.status == TicketStatus.pending,
    Ticket.assigned_agent_id == None,
    Chat.mode == ChatMode.paused,
).all()
if not available2:
    print("  [GAGAL] Masih kosong - ada masalah di query atau model")
else:
    for c in available2:
        print(f"  ✓ Muncul di queue: chat_id={c.id} | phone={c.customer_phone}")
    print()
    print("  ✅ Query BENAR. Kalau di frontend masih kosong, kemungkinan:")
    print("     - Backend belum di-restart setelah perubahan kode")
    print("     - Ticket yang ada di DB punya mode chat bukan 'paused'")
    print("     - Endpoint /chats/queue/available gagal (cek log backend)")

# ─── 6. CLEANUP ───────────────────────────────────────────────
print()
print(SEP)
print("6. CLEANUP data test")
print(SEP)
db.query(Ticket).filter(Ticket.chat_id == test_chat.id).delete()
db.delete(test_chat)
db.commit()
print("  [OK] Data test dihapus")

print()
print(SEP)
print("SELESAI")
print(SEP)
db.close()
