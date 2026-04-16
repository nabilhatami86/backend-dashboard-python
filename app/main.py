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
# Force webhook logger to show INFO regardless of uvicorn override
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

# Import models to register with SQLAlchemy
from app.models.user import User
from app.models.chat import Chat
from app.models.message import Message
from app.models.admin_message import AdminMessage
from app.models.ticket import Ticket
from app.models.agent_profile import AgentProfile
from app.models.queue_assignment import QueueAssignment
from app.models.agent_metrics import AgentMetrics
from app.models.shortcut_message import ShortcutMessage

# Create tables
Base.metadata.create_all(bind=engine)

# =========================================================
# APP CONFIGURATION
# =========================================================
APP_NAME = "Dashboard API"
APP_VERSION = "0.1.0"
ENV = os.getenv("NODE_ENV", "development")
PORT = os.getenv("PORT", "8000")

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
)

# =========================================================
# CORS
# =========================================================
# Development: Allow all origins
# Production: Restrict to specific origins
if ENV == "production":
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8888",
        "http://127.0.0.1:8888",
    ]
else:
    # Development: Allow all origins
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True if ENV == "production" else False,  # Can't use credentials with allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# HELPER FUNCTIONS
# =========================================================
def section(title: str):
    print("\n" + "─" * 80)
    print(title)
    print("─" * 80)

def mask(value: str):
    if not value:
        return "Not Set"
    return "****" + value[-4:] if len(value) > 4 else "****"

# =========================================================
# STARTUP DASHBOARD (PROFESSIONAL)
# =========================================================
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
║              🚀  D A S H B O A R D   A P I   S T A R T U P                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""" + "\033[0m")
    # APP INFO
    section("🚀 APPLICATION INFO")
    print(f"📦 App        : {APP_NAME}")
    print(f"📌 Version    : {APP_VERSION}")
    print(f"🌎 Environment: {ENV}")
    print(f"⏰ Started at : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 Workdir    : {os.getcwd()}")

    # DATABASE
    section("🗄️ DATABASE")
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

    # MODELS
    section(f"📚 MODELS LOADED ({len(Base.metadata.tables)})")
    for model in Base.metadata.tables.keys():
        print(f"   ├─ {model}")

    # ROUTES
    section("🛣️ API ROUTES")
    routes = [
        ("Auth", "/api/auth"),
        ("Chat", "/api/chats"),
        ("Users", "/api/users"),
        ("Admin Chat", "/api/admin/chats"),
        ("Tickets", "/api/tickets"),
        ("Agent Chat", "/api/agent/chats"),
        ("Shortcuts", "/api/shortcuts"),
        ("WhatsApp", "/api/webhook"),
    ]
    for name, path in routes:
        print(f"   ├─ {name.ljust(12)} → {path}")

    # CORS
    section("🌐 CORS")
    print("   Origins    : http://localhost:3000, http://127.0.0.1:3000")
    print("   Credentials: Enabled")
    print("   Methods    : All")
    print("   Headers    : All")

    # DOCUMENTATION
    section("📘 API DOCUMENTATION")
    print(f"   Swagger UI : {base_url}/docs")
    print(f"   ReDoc     : {base_url}/redoc")
    print(f"   OpenAPI   : {base_url}/openapi.json")

    # ENVIRONMENT
    section("🔧 ENVIRONMENT")
    env_vars = [
        "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER",
        "SECRET_KEY", "WHAPI_TOKEN", "WHAPI_URL"
    ]
    for var in env_vars:
        value = os.getenv(var)
        if var in ["SECRET_KEY", "WHAPI_TOKEN"]:
            print(f"   ├─ {var.ljust(12)} : {mask(value)}")
        else:
            print(f"   ├─ {var.ljust(12)} : {value or 'Not Set'}")

    print("\n" + "=" * 80)
    print("✅ APPLICATION READY")
    print("=" * 80 + "\n")


# =========================================================
# AGENT ONLINE STATUS — STARTUP RESET
# =========================================================
@app.on_event("startup")
def reset_all_agents_to_offline():
    """
    Saat server baru start, semua agent di-reset ke offline.
    Agent harus buka dashboard lagi agar statusnya kembali online.
    """
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


# =========================================================
# AGENT ONLINE STATUS — STALE AGENT BACKGROUND TASK
# =========================================================
async def _stale_agent_checker():
    """
    Background task: cek setiap 2 menit.
    Agent yang tidak kirim heartbeat > 3 menit → set offline + broadcast WS.
    """
    logger = logging.getLogger(__name__)
    while True:
        await asyncio.sleep(120)  # cek setiap 2 menit
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


# =========================================================
# STATIC FILES (uploads)
# =========================================================
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# =========================================================
# ROUTES
# =========================================================
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(users.router)
app.include_router(admin_chat.router)
app.include_router(tickets.router)
app.include_router(agent_chat.router)
app.include_router(shortcuts.router)
app.include_router(ws_router)
app.include_router(whapi_router)

# =========================================================
# HEALTH ENDPOINTS
# =========================================================
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
