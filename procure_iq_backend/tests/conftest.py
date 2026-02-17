"""
Pytest configuration and fixtures for ProcureIQ tests.

This file provides reusable test fixtures for database, API client, and mock data.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app import models


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh database session for each test.
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    Create a test client with overridden database dependency.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def api_key():
    """
    Return a test API key.
    """
    return "test_api_key_12345"


@pytest.fixture
def auth_headers(api_key):
    """
    Return headers with API key authentication.
    """
    return {"X-API-Key": api_key}


@pytest.fixture
def sample_vendor(db_session):
    """
    Create a sample vendor in the database.
    """
    vendor = models.Vendor(
        name="Acme Corporation",
        contact_email="contact@acme.com",
        contact_phone="+1234567890",
        active=True,
        aliases=["Acme Corp", "ACME", "Acme Inc"]
    )
    db_session.add(vendor)
    db_session.commit()
    db_session.refresh(vendor)
    return vendor


@pytest.fixture
def sample_invoice(db_session, sample_vendor):
    """
    Create a sample invoice in the database.
    """
    invoice = models.Invoice(
        invoice_number="INV-2024-001",
        vendor_id=sample_vendor.id,
        amount=1500.00,
        invoice_date="2024-02-15",
        status="pending",
        confidence_score=92.5,
        match_method="gemini",
        extracted_data={"items": [{"description": "MacBook Pro", "quantity": 1, "price": 1500.00}]}
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


@pytest.fixture
def sample_inventory_item(db_session):
    """
    Create a sample inventory item.
    """
    item = models.InventoryItem(
        name="MacBook Pro M3",
        brand="Apple",
        quantity=45,
        reorder_threshold=50,
        reorder_quantity=10,
        unit_price=1999.0,
        sku="APL-MBP-M3"
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


@pytest.fixture
def mock_ai_response():
    """
    Return a mock AI response for testing.
    """
    return {
        "vendor_id": 1,
        "confidence": 95.0,
        "reasoning": "High confidence match based on exact name match",
        "method": "gemini"
    }
