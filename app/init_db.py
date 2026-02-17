"""
Database initialization script for Procure-IQ v2.0

Creates all tables and seeds sample data for testing:
- 3 sample vendors
- 20 sample inventory items (some with low stock)
- Vendor aliases for testing

Run this script to initialize a fresh database:
    python -m app.init_db
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, SessionLocal
from app import models
import datetime

def init_database():
    """Create all tables and seed sample data."""
    
    print("Creating database tables...")
    models.Base.metadata.create_all(bind=engine)
    print("[OK] Tables created")
    
    db = SessionLocal()
    
    try:
        # Check if data already exists
        existing_vendors = db.query(models.Vendor).count()
        if existing_vendors > 0:
            print(f"Database already has {existing_vendors} vendors. Skipping seed data.")
            return
        
        print("\nSeeding sample data...")
        
        # 1. Create sample vendors
        vendors = [
            models.Vendor(id=1, name="ACME Corporation", email="orders@acme.com", active=True),
            models.Vendor(id=2, name="Beta Supplies Inc", email="sales@betasupplies.com", active=True),
            models.Vendor(id=3, name="Gamma Industrial", email="info@gammaindustrial.com", active=True),
        ]
        
        for vendor in vendors:
            db.add(vendor)
        
        db.commit()
        print(f"[OK] Created {len(vendors)} vendors")
        
        # 2. Create vendor aliases
        aliases = [
            models.VendorAlias(alias_name="Acme Corp", vendor_id=1, confidence=95),
            models.VendorAlias(alias_name="ACME", vendor_id=1, confidence=100),
            models.VendorAlias(alias_name="Beta Supplies", vendor_id=2, confidence=90),
        ]
        
        for alias in aliases:
            db.add(alias)
        
        db.commit()
        print(f"[OK] Created {len(aliases)} vendor aliases")
        
        # 3. Create sample inventory items (20 items, some with low stock)
        inventory_items = [
            # Low stock items (will trigger alerts)
            models.InventoryItem(name="Widget A", quantity=5, reorder_threshold=10, reorder_quantity=50, supplier_id=1, unit_price=12.50, sku="WGT-A-001"),
            models.InventoryItem(name="Gadget B", quantity=3, reorder_threshold=10, reorder_quantity=30, supplier_id=2, unit_price=25.00, sku="GDG-B-002"),
            models.InventoryItem(name="Component C", quantity=8, reorder_threshold=15, reorder_quantity=100, supplier_id=1, unit_price=5.75, sku="CMP-C-003"),
            models.InventoryItem(name="Tool D", quantity=2, reorder_threshold=5, reorder_quantity=20, supplier_id=3, unit_price=45.00, sku="TOL-D-004"),
            
            # Normal stock items
            models.InventoryItem(name="Bolt Set E", quantity=150, reorder_threshold=50, reorder_quantity=200, supplier_id=1, unit_price=8.99, sku="BLT-E-005"),
            models.InventoryItem(name="Screw Pack F", quantity=200, reorder_threshold=75, reorder_quantity=300, supplier_id=2, unit_price=6.50, sku="SCR-F-006"),
            models.InventoryItem(name="Washer Kit G", quantity=180, reorder_threshold=60, reorder_quantity=250, supplier_id=1, unit_price=4.25, sku="WSH-G-007"),
            models.InventoryItem(name="Nut Assortment H", quantity=120, reorder_threshold=40, reorder_quantity=150, supplier_id=3, unit_price=7.80, sku="NUT-H-008"),
            models.InventoryItem(name="Bearing I", quantity=45, reorder_threshold=20, reorder_quantity=60, supplier_id=2, unit_price=18.50, sku="BRG-I-009"),
            models.InventoryItem(name="Gasket J", quantity=90, reorder_threshold=30, reorder_quantity=120, supplier_id=1, unit_price=3.25, sku="GSK-J-010"),
            
            # More items
            models.InventoryItem(name="Cable K", quantity=75, reorder_threshold=25, reorder_quantity=100, supplier_id=2, unit_price=15.00, sku="CBL-K-011"),
            models.InventoryItem(name="Connector L", quantity=110, reorder_threshold=35, reorder_quantity=150, supplier_id=3, unit_price=9.75, sku="CON-L-012"),
            models.InventoryItem(name="Switch M", quantity=60, reorder_threshold=20, reorder_quantity=80, supplier_id=1, unit_price=22.50, sku="SWT-M-013"),
            models.InventoryItem(name="Relay N", quantity=40, reorder_threshold=15, reorder_quantity=50, supplier_id=2, unit_price=28.00, sku="RLY-N-014"),
            models.InventoryItem(name="Fuse O", quantity=95, reorder_threshold=30, reorder_quantity=120, supplier_id=3, unit_price=2.50, sku="FUS-O-015"),
            models.InventoryItem(name="Resistor P", quantity=250, reorder_threshold=80, reorder_quantity=300, supplier_id=1, unit_price=0.75, sku="RES-P-016"),
            models.InventoryItem(name="Capacitor Q", quantity=180, reorder_threshold=60, reorder_quantity=200, supplier_id=2, unit_price=1.25, sku="CAP-Q-017"),
            models.InventoryItem(name="Diode R", quantity=140, reorder_threshold=45, reorder_quantity=180, supplier_id=3, unit_price=1.50, sku="DIO-R-018"),
            models.InventoryItem(name="Transistor S", quantity=85, reorder_threshold=30, reorder_quantity=100, supplier_id=1, unit_price=3.00, sku="TRN-S-019"),
            models.InventoryItem(name="IC Chip T", quantity=55, reorder_threshold=20, reorder_quantity=70, supplier_id=2, unit_price=12.00, sku="ICP-T-020"),
        ]
        
        for item in inventory_items:
            db.add(item)
        
        db.commit()
        print(f"[OK] Created {len(inventory_items)} inventory items")
        
        # Count low stock items
        low_stock_count = sum(1 for item in inventory_items if item.quantity <= item.reorder_threshold)
        print(f"  - {low_stock_count} items are below reorder threshold (will trigger alerts)")
        
        print("\n[SUCCESS] Database initialization complete!")
        print(f"\nSummary:")
        print(f"  - Vendors: {len(vendors)}")
        print(f"  - Vendor Aliases: {len(aliases)}")
        print(f"  - Inventory Items: {len(inventory_items)}")
        print(f"  - Low Stock Items: {low_stock_count}")
        
    except Exception as e:
        print(f"\n[ERROR] Error during initialization: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
