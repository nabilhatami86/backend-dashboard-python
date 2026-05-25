from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from datetime import datetime, timedelta
import asyncio
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(name)s: %(message)s",
)
# Pastikan webhook logger tetap tampil meski uvicorn override level logging
logging.getLogger("app.whapi.webhook").setLevel(logging.INFO)
logging.getLogger("app.services.bot_service").setLevel(logging.INFO)

from app.config.database import engine, Base
from app.config.deps import get_db
from app.config.config import DB_HOST, DB_PORT, DB_NAME, DB_USER

from app.routes import auth, chat, users, admin_chat, tickets, agent_chat, shortcuts
from app.routes.ws import router as ws_router
from app.whapi.webhook import router as whapi_router
from app.config.database import SessionLocal
from app.services.ws_manager import manager as ws_manager

# Import model supaya SQLAlchemy mendaftarkan semua tabel sebelum create_all
from app.models.user import User
from app.models.chat import Chat
from app.models.message import Message
from app.models.admin_message import AdminMessage
from app.models.ticket import Ticket
from app.models.agent_profile import AgentProfile
from app.models.queue_assignment import QueueAssignment
from app.models.agent_metrics import AgentMetrics
from app.models.shortcut_message import ShortcutMessage

Base.metadata.create_all(bind=engine)

APP_NAME = "Dashboard API"
APP_VERSION = "0.1.0"
ENV = os.getenv("NODE_ENV", "development")
PORT = os.getenv("PORT", "8000")

app = FastAPI(title=APP_NAME, version=APP_VERSION)

# Production: batasi origin. Development: izinkan semua.
if ENV == "production":
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8888",
        "http://127.0.0.1:8888",
    ]
else:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=ENV == "production",  # tidak bisa pakai credentials dengan allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


def section(title: str):
    print("\n" + "─" * 80)
    print(title)
    print("─" * 80)


def mask(value: str):
    if not value:
        return "Not Set"
    return "****" + value[-4:] if len(value) > 4 else "****"


@app.on_event("startup")
def startup_dashboard():
    base_url = f"http://localhost:{PORT}"

    print("\033[36m" + """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██████╗  █████╗ ███████╗██╗  ██╗██████╗  █████╗ ██████╗ ██████╗            ║
║   ██╔══██╗██╔══██╗██╔════╝██║  ██║██╔══██╗██╔══██╗██╔══██╗██╔══██╗           ║
║   ██║  ██║███████║███████╗███████║██████╔╝███████║██████╔╝██║  ██║           ║
║   ██║  ██║██╔══██║╚════██║██╔══██║██╔══██╗██╔══██║██╔══██╗██║  ██║           ║
║   ██████╔╝██║  ██║███████║██║  ██║██████╔╝██║  ██║██║  ██║██████╔╝           ║
║   ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝            ║
║                                                                              ║
║              D A S H B O A R D   A P I   S T A R T U P                      ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""" + "\033[0m")

    section("APPLICATION INFO")
    print(f"   App        : {APP_NAME}")
    print(f"   Version    : {APP_VERSION}")
    print(f"   Environment: {ENV}")
    print(f"   Started at : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Workdir    : {os.getcwd()}")

    section("DATABASE")
    print(f"   Type       : PostgreSQL")
    print(f"   Host       : {DB_HOST}")
    print(f"   Port       : {DB_PORT}")
    print(f"   Database   : {DB_NAME}")
    print(f"   User       : {DB_USER}")

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            inspector = inspect(engine)
            tables = inspector.get_table_names()
        print(f"   Status     : CONNECTED")
        print(f"   Tables     : {len(tables)}")
        for table in tables:
            print(f"   ├─ {table}")
    except Exception as e:
        print(f"   Status     : FAILED")
        print(f"   Error      : {e}")

    section(f"MODELS LOADED ({len(Base.metadata.tables)})")
    for model in Base.metadata.tables.keys():
        print(f"   ├─ {model}")

    section("API ROUTES")
    routes = [
        ("Auth",       "/api/auth"),
        ("Chat",       "/api/chats"),
        ("Users",      "/api/users"),
        ("Admin Chat", "/api/admin/chats"),
        ("Tickets",    "/api/tickets"),
        ("Agent Chat", "/api/agent/chats"),
        ("Shortcuts",  "/api/shortcuts"),
        ("WhatsApp",   "/api/webhook"),
    ]
    for name, path in routes:
        print(f"   ├─ {name.ljust(12)} → {path}")

    section("API DOCUMENTATION")
    print(f"   Swagger UI : {base_url}/docs")
    print(f"   ReDoc      : {base_url}/redoc")
    print(f"   OpenAPI    : {base_url}/openapi.json")

    section("ENVIRONMENT")
    env_vars = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "SECRET_KEY", "WHAPI_TOKEN", "WHAPI_URL"]
    for var in env_vars:
        value = os.getenv(var)
        if var in ["SECRET_KEY", "WHAPI_TOKEN"]:
            print(f"   ├─ {var.ljust(12)} : {mask(value)}")
        else:
            print(f"   ├─ {var.ljust(12)} : {value or 'Not Set'}")

    print("\n" + "=" * 80)
    print("APPLICATION READY")
    print("=" * 80 + "\n")


@app.on_event("startup")
def sync_ticket_priority_from_chats():
    """Sinkronisasi Ticket.priority dari Chat.priority untuk semua record yang ada."""
    from app.models.chat import Chat
    from app.models.ticket import Ticket as TicketModel, TicketPriority
    db = SessionLocal()
    try:
        tickets = db.query(TicketModel).all()
        updated = 0
        for ticket in tickets:
            chat = db.query(Chat).filter(Chat.id == ticket.chat_id).first()
            if chat and chat.priority:
                try:
                    new_priority = TicketPriority[chat.priority]
                    if ticket.priority != new_priority:
                        ticket.priority = new_priority
                        updated += 1
                except KeyError:
                    pass
        if updated:
            db.commit()
            logging.getLogger(__name__).info(f"[MIGRATION] Synced priority for {updated} ticket(s)")
    except Exception as e:
        logging.getLogger(__name__).error(f"[MIGRATION] sync_ticket_priority failed: {e}")
    finally:
        db.close()


@app.on_event("startup")
def reset_all_agents_to_offline():
    """Reset semua agent ke offline saat server start. Agent harus buka dashboard lagi."""
    from app.models.agent_profile import AgentProfile, AgentStatus
    db = SessionLocal()
    try:
        count = db.query(AgentProfile).filter(
            AgentProfile.status == AgentStatus.online
        ).update({
            "status": AgentStatus.offline,
            "is_available": False,
        })
        db.commit()
        if count:
            logging.getLogger(__name__).info(f"[STARTUP] Reset {count} agent(s) to offline")
    except Exception as e:
        logging.getLogger(__name__).error(f"[STARTUP] Failed to reset agents: {e}")
    finally:
        db.close()


async def _stale_agent_checker():
    """
    Background task: cek setiap 2 menit.
    Agent yang tidak kirim heartbeat lebih dari 3 menit → set offline dan broadcast WS.
    """
    logger = logging.getLogger(__name__)
    while True:
        await asyncio.sleep(120)
        try:
            from app.models.agent_profile import AgentProfile, AgentStatus
            from sqlalchemy import or_
            db = SessionLocal()
            try:
                cutoff = datetime.now() - timedelta(minutes=3)
                stale = db.query(AgentProfile).filter(
                    AgentProfile.status == AgentStatus.online,
                    or_(
                        AgentProfile.last_activity_at == None,
                        AgentProfile.last_activity_at < cutoff,
                    )
                ).all()

                for profile in stale:
                    profile.status = AgentStatus.offline
                    profile.is_available = False
                    await ws_manager.broadcast_global({
                        "type": "agent_status",
                        "agent_id": profile.user_id,
                        "name": profile.user.name,
                        "display_name": profile.display_name,
                        "status": "offline",
                        "is_available": False,
                    })

                if stale:
                    db.commit()
                    logger.info(f"[STALE-CHECKER] Marked {len(stale)} agent(s) offline")
            finally:
                db.close()
        except Exception as e:
            logging.getLogger(__name__).error(f"[STALE-CHECKER] Error: {e}")


@app.on_event("startup")
async def start_stale_agent_checker():
    asyncio.create_task(_stale_agent_checker())


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(users.router)
app.include_router(admin_chat.router)
app.include_router(tickets.router)
app.include_router(agent_chat.router)
app.include_router(shortcuts.router)
app.include_router(ws_router)
app.include_router(whapi_router)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok"}


@app.get("/db-connect", tags=["Health"])
def db_connect(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"database": "postgresql", "status": "connected"}
