from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from app.whapi.webhook import router as whapi_router
import os
from datetime import datetime

from app.config.database import engine, Base
from app.config.deps import get_db
from app.config.config import DB_HOST, DB_PORT, DB_NAME, DB_USER
from app.routes import auth, chat, users, admin_chat, tickets, agent_chat

# Import models to ensure they're registered with Base
from app.models.user import User
from app.models.chat import Chat
from app.models.message import Message
from app.models.admin_message import AdminMessage
from app.models.ticket import Ticket
from app.models.agent_profile import AgentProfile
from app.models.queue_assignment import QueueAssignment
from app.models.agent_metrics import AgentMetrics

# create tables
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Dashboard API",
    version="0.1.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_db_check():
    print("\n" + "="*80)
    print("🚀 DASHBOARD API STARTUP INFO")
    print("="*80)

    # Time info
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Project info
    print(f"\n📦 Project: Dashboard API v0.1.0")
    print(f"📂 Working Directory: {os.getcwd()}")

    # Database info
    print(f"\n🗄️  DATABASE CONNECTION:")
    print(f"   ├─ Host: {DB_HOST}")
    print(f"   ├─ Port: {DB_PORT}")
    print(f"   ├─ Database: {DB_NAME}")
    print(f"   ├─ User: {DB_USER}")
    print(f"   └─ Type: PostgreSQL")

    # Test connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

            # Get table count
            inspector = inspect(engine)
            tables = inspector.get_table_names()

        print(f"   ✅ Status: CONNECTED")
        print(f"   📊 Total Tables: {len(tables)}")
        print(f"   📋 Tables: {', '.join(tables)}")

    except Exception as e:
        print(f"   ❌ Status: CONNECTION FAILED")
        print(f"   ⚠️  Error: {e}")

    # Models info
    print(f"\n📚 LOADED MODELS ({len(Base.metadata.tables)}):")
    for table_name in Base.metadata.tables.keys():
        print(f"   ├─ {table_name}")

    # Routes info
    print(f"\n🛣️  API ROUTES:")
    routes = [
        ("Auth", "/api/auth", ["login", "register", "logout"]),
        ("Chat", "/api/chats", ["list", "create", "update", "delete"]),
        ("Users", "/api/users", ["list", "profile", "update"]),
        ("Admin Chat", "/api/admin/chats", ["list", "assign", "messages"]),
        ("Tickets", "/api/tickets", ["list", "stats", "create", "update"]),
        ("Agent Chat", "/api/agent/chats", ["queue", "claim", "messages"]),
        ("WhatsApp", "/api/webhook", ["whapi webhook handler"]),
    ]

    for name, path, endpoints in routes:
        print(f"   ├─ {name:12} → {path:20} ({', '.join(endpoints)})")

    # CORS info
    print(f"\n🌐 CORS CONFIGURATION:")
    print(f"   ├─ Allowed Origins: http://localhost:3000, http://127.0.0.1:3000")
    print(f"   ├─ Credentials: Enabled")
    print(f"   ├─ Methods: All")
    print(f"   └─ Headers: All")

    # Environment
    print(f"\n🔧 ENVIRONMENT:")
    env_vars = [
        "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER",
        "SECRET_KEY", "WHAPI_TOKEN", "WHAPI_URL"
    ]
    for var in env_vars:
        value = os.getenv(var)
        if value:
            if var in ["DB_PASSWORD", "SECRET_KEY", "WHAPI_TOKEN"]:
                display = "***" + value[-4:] if len(value) > 4 else "****"
            else:
                display = value
            print(f"   ├─ {var}: {display}")
        else:
            print(f"   ├─ {var}: Not Set")

    print("\n" + "="*80)
    print("✅ APPLICATION READY")
    print("="*80 + "\n")


# routes
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(users.router)
app.include_router(admin_chat.router)
app.include_router(tickets.router)
app.include_router(agent_chat.router)
app.include_router(whapi_router)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok"}


@app.get("/db-connect", tags=["Health"])
def db_connect(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "database": "postgresql",
        "status": "connected"
    }
