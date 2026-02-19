from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
import os

# Ensure the database stays in the backend folder
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "procure_iq.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Configure SQLite for concurrent writes
# - WAL mode: Write-Ahead Logging for better concurrency
# - timeout: 30 seconds to wait for locks
# - check_same_thread: False allows multi-threading
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={
        "check_same_thread": False,
        "timeout": 30
    }
)

# Enable WAL (Write-Ahead Logging) mode for better concurrent write performance
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Configure SQLite connection for optimal concurrent access.
    WAL mode allows multiple readers and one writer simultaneously.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
