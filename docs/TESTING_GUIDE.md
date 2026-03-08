# 🧪 Panduan Testing - Agent Warung Madura

## 📋 Yang Sudah Diupdate

### 1. Bot AI Responses (`app/services/bot_service.py`)
Bot sekarang support keyword detection untuk skenario Agent Warung Madura:

| Keyword | Bot Response |
|---------|--------------|
| stock, stok, habis, kosong, restock | "Baik, saya catat masalah stock Anda. Untuk restock biasanya 1-2 hari kerja. Admin akan segera membantu koordinasi stock Anda." |
| bayar, pembayaran, transfer, uang | "Terima kasih laporannya. Tim admin akan segera cek transaksi pembayaran Anda. Mohon tunggu sebentar." |
| error, sistem, gak bisa, tidak bisa | "Maaf atas kendalanya. Tim teknis akan segera memeriksa masalah sistem Anda. Mohon tunggu max 15 menit." |
| kirim, pengiriman, telat, terlambat | "Mohon maaf atas keterlambatan pengiriman. Admin akan koordinasi dengan tim logistik dan segera menghubungi Anda." |
| promo, diskon, promosi | "Untuk info promo terbaru, admin akan segera informasikan ke Anda. Terima kasih sudah bertanya." |
| komplain, keluhan, kecewa | "Mohon maaf atas ketidaknyamanan yang Anda alami. Admin akan segera menghubungi dan membantu menyelesaikan masalah ini." |

### 2. Test Webhook Script (`test_webhook.py`)
Script testing interaktif dengan 6 skenario siap pakai:
- Stock Habis
- Masalah Pembayaran
- Sistem Error
- Promo
- Komplain Pengiraman
- Custom Message

---

## 🚀 Cara Testing

### Step 1: Pastikan Backend Running
```bash
cd /Users/mm/Desktop/Dashboard/backend-dashboard-python
python3 -m uvicorn app.main:app --reload
```

Pastikan muncul:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Step 2: Pastikan Frontend Running
```bash
cd /Users/mm/Desktop/Dashboard/dashboard-message-center
npm run dev
```

Pastikan muncul:
```
ready - started server on 0.0.0.0:3000
```

### Step 3: Run Test Script

#### Option A: Interactive Menu (Recommended)
```bash
cd /Users/mm/Desktop/Dashboard/backend-dashboard-python/backend-dashboard-python.backup
python3 test_webhook.py
```

Akan muncul menu:
```
============================================================
TESTING AGENT WARUNG MADURA - WEBHOOK SIMULATOR
============================================================

Pilih Skenario Test:
------------------------------------------------------------
1. Stock Habis
   Pesan: "Min, stock indomie goreng habis. Kapan bisa restock?"
2. Masalah Pembayaran
   Pesan: "Admin, ada customer bayar tapi belum masuk ke sistem"
3. Sistem Error
   Pesan: "Sistemnya error, gak bisa input pesanan baru"
4. Promo
   Pesan: "Min, ada promo bulan ini gak? Customer banyak yang nanya"
5. Komplain Pengiriman
   Pesan: "Pengiriman kemarin telat 3 jam, customer komplain"
6. Custom Message
------------------------------------------------------------
0. Exit

Pilih skenario (0-6):
```

Pilih nomor 1-6, lalu Enter.

#### Option B: Quick Test
```bash
python3 test_webhook.py --quick
```

Langsung kirim skenario default (Stock Habis).

### Step 4: Lihat Hasil di Dashboard

1. Buka browser: http://localhost:3000/login
2. Login dengan:
   - Username: `admin`
   - Password: `admin123`
3. Chat akan muncul di sidebar kiri (tunggu max 5 detik karena auto-refresh)
4. Klik chat untuk lihat:
   - Pesan dari agent (warung)
   - Bot response otomatis
5. Klik "Assign" untuk switch ke mode agent
6. Ketik balasan manual dari admin

---

## 📊 Test Scenarios Detail

### Skenario 1: Stock Habis
```
Agent: "Min, stock indomie goreng habis. Kapan bisa restock?"
Bot: "Baik, saya catat masalah stock Anda. Untuk restock biasanya
      1-2 hari kerja. Admin akan segera membantu koordinasi stock Anda."
```

**Expected Result:**
- Chat muncul dengan nama "Warung Pak Budi"
- Bot auto-reply tentang restock
- Mode: BOT (biru)

### Skenario 2: Masalah Pembayaran
```
Agent: "Admin, ada customer bayar tapi belum masuk ke sistem"
Bot: "Terima kasih laporannya. Tim admin akan segera cek transaksi
      pembayaran Anda. Mohon tunggu sebentar."
```

**Expected Result:**
- Chat dari "Warung Bu Siti"
- Bot response supportif
- Admin bisa assign untuk manual handle

### Skenario 3: Sistem Error
```
Agent: "Sistemnya error, gak bisa input pesanan baru"
Bot: "Maaf atas kendalanya. Tim teknis akan segera memeriksa
      masalah sistem Anda. Mohon tunggu max 15 menit."
```

**Expected Result:**
- Chat dari "Warung Mas Agus"
- Bot memberikan estimasi waktu
- Urgent case - admin should respond quickly

### Skenario 4: Promo
```
Agent: "Min, ada promo bulan ini gak? Customer banyak yang nanya"
Bot: "Untuk info promo terbaru, admin akan segera informasikan
      ke Anda. Terima kasih sudah bertanya."
```

### Skenario 5: Komplain Pengiriman
```
Agent: "Pengiriman kemarin telat 3 jam, customer komplain"
Bot: "Mohon maaf atas keterlambatan pengiriman. Admin akan koordinasi
      dengan tim logistik dan segera menghubungi Anda."
```

### Skenario 6: Custom Message
Anda bisa input pesan custom untuk test keyword detection lainnya.

---

## 🔍 Troubleshooting

### Chat tidak muncul di dashboard?

**Cek 1:** Backend receiving webhook?
```bash
# Lihat terminal backend, pastikan ada log:
# INFO: Received WhatsApp message from...
```

**Cek 2:** Chat ada di database?
```bash
# Get token dulu
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"identifier":"admin","password":"admin123"}'

# Copy access_token, lalu:
curl "http://localhost:8000/chats/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Cek 3:** Frontend auto-refresh?
- Dashboard auto-refresh setiap 5 detik
- Tunggu maksimal 5 detik setelah kirim test
- Atau refresh browser manual (F5)

### Bot tidak auto-reply?

**Cek:** Mode chat di database
```bash
# Chat mode should be "bot", not "agent" or "paused"
```

### Response tidak sesuai keyword?

**Cek:** Keyword di `bot_service.py` line 49-94
- Pastikan keyword ada di list
- Case insensitive (sudah di-lowercase)
- Bisa tambah keyword baru sesuai kebutuhan

---

## 🎯 Testing Checklist

- [ ] Backend running (port 8000)
- [ ] Frontend running (port 3000)
- [ ] Test script bisa connect ke backend
- [ ] Skenario 1: Stock Habis - Bot response ✅
- [ ] Skenario 2: Pembayaran - Bot response ✅
- [ ] Skenario 3: Error Sistem - Bot response ✅
- [ ] Skenario 4: Promo - Bot response ✅
- [ ] Skenario 5: Komplain - Bot response ✅
- [ ] Chat muncul di dashboard sidebar
- [ ] Bot response sesuai keyword
- [ ] Admin bisa assign to agent mode
- [ ] Admin bisa reply manual
- [ ] Customer detail panel shows warung info

---

## 📝 Next Steps - Production Ready

1. **Deploy Backend:**
   - Setup production database (PostgreSQL)
   - Configure WHAPI credentials
   - Setup webhook URL di WHAPI dashboard

2. **Connect Real WhatsApp:**
   - Scan QR code di WHAPI
   - Update webhook endpoint
   - Test dengan WhatsApp real

3. **Improve Bot Responses:**
   - Tambah keyword detection
   - Setup OpenAI API key untuk AI responses
   - Fine-tune prompts untuk context Warung Madura

4. **Add Features:**
   - Notification untuk urgent messages
   - Auto-assign berdasarkan keyword
   - Analytics dashboard
   - Export chat history

---

## 🎉 Selamat Testing!

Jika ada error atau pertanyaan:
1. Check terminal backend untuk error logs
2. Check browser console (F12) untuk frontend errors
3. Verify database dengan curl commands di atas

**Happy Testing!** 🚀
