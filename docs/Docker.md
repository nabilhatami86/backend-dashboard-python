# 🐳 Docker Setup – Backend ASMI (FastAPI + PostgreSQL)

Dokumentasi ini menjelaskan cara menjalankan **Backend ASMI** menggunakan **Docker & Docker Compose**, termasuk setup database, environment, dan migration.

---

## 📦 Tech Stack

- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic (Migration)
- Docker & Docker Compose

---

## 📁 Struktur File Penting

```
backend-asmi-python/
├── app/
├── alembic/
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── .env
├── requirements.txt
└── README.md
```

---

## 🔐 Environment Variable

Buat file **.env** di root project:

```env
DB_HOST=db
DB_PORT=5432
DB_NAME=asmi_db
DB_USER=postgres
DB_PASSWORD=123

SECRET_KEY=super-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60000
```

> ⚠️ `DB_HOST=db` **WAJIB** karena nama service PostgreSQL di docker-compose

---

## 🐳 Dockerfile

Pastikan file **Dockerfile** sudah ada:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 🧱 docker-compose.yml

```yaml
services:
  api:
    build: .
    container_name: asmi-backend
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - db

  db:
    image: postgres:16
    container_name: asmi-postgres
    restart: always
    environment:
      POSTGRES_DB: asmi_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: 123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## 🚀 Menjalankan Aplikasi

### 1️⃣ Build & Run Container

```bash
docker compose up --build
```

Akses API:

```
http://localhost:8000
```

Swagger:

```
http://localhost:8000/docs
```

---

## 🗄️ Database Migration (Alembic)

### Masuk ke container backend

```bash
docker compose exec api bash
```

### Jalankan migration

```bash
alembic upgrade head
```

### (Opsional) Generate migration baru

```bash
alembic revision --autogenerate -m "message"
```

---

## 🔄 Restart & Stop

Stop container:

```bash
docker compose down
```

Stop + hapus volume DB:

```bash
docker compose down -v
```

---

## ✅ Checklist Jika Error

- Docker Desktop **sudah running**
- `.env` ada di root project
- `DB_HOST=db` (bukan localhost)
- Migration sudah dijalankan

---

## 📌 Catatan Penting

- Jangan commit file `.env`
- Migration Alembic **wajib dijalankan** saat pertama deploy
- Gunakan volume agar data PostgreSQL tidak hilang

---
