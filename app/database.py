from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
import os, sys

# Import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Configure engine — SQLite needs special args, Postgres does not
_connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False, "timeout": 30}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=_connect_args)

# Enable WAL mode ONLY for SQLite (Postgres handles concurrency natively)
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """Configure SQLite for optimal concurrent access."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
