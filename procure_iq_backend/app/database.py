from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os

# Ensure the database stays in the backend folder
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "procure_iq.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
