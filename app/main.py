from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.whapi.webhook import router as whapi_router

from app.config.database import engine, Base
from app.config.deps import get_db
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
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ PostgreSQL CONNECTED")
    except Exception as e:
        print("❌ PostgreSQL CONNECTION FAILED:", e)


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
