"""
Database initialization script for Procure-IQ v2.0

Creates all tables and seeds sample data for testing:
- 3 sample vendors + 15 ERP vendors
- 20 sample inventory items (some with low stock)
- 20 purchase orders, 15 goods receipts
- Vendor aliases for testing
- Default ERP connection (Python Sample DB)

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


def seed_erp_data(db):
    """Seed Python ERP DB with realistic data for demo."""
    
    # Skip if already seeded
    if db.query(models.GoodsReceipt).count() > 0:
        print("[SKIP] ERP data already seeded")
        return
    
    print("\nSeeding ERP data (vendors, POs, receipts)...")
    
    # --- Ensure we have enough vendors (add more if needed) ---
    existing_count = db.query(models.Vendor).count()
    
    erp_vendors = [
        models.Vendor(name="TCS Limited", email="procurement@tcs.com", active=True),
        models.Vendor(name="Infosys Technologies", email="vendor@infosys.com", active=True),
        models.Vendor(name="Wipro Enterprises", email="sales@wipro.com", active=True),
        models.Vendor(name="HCL Technologies", email="orders@hcl.com", active=True),
        models.Vendor(name="Tech Mahindra", email="billing@techmahindra.com", active=True),
        models.Vendor(name="L&T Infotech", email="support@lntinfotech.com", active=True),
        models.Vendor(name="Mphasis Ltd", email="accounts@mphasis.com", active=True),
        models.Vendor(name="Mindtree Solutions", email="procurement@mindtree.com", active=True),
        models.Vendor(name="Cyient Ltd", email="sales@cyient.com", active=True),
        models.Vendor(name="Persistent Systems", email="orders@persistent.com", active=True),
        models.Vendor(name="Coforge Limited", email="billing@coforge.com", active=True),
        models.Vendor(name="Zensar Technologies", email="vendor@zensar.com", active=True),
    ]
    db.add_all(erp_vendors)
    db.commit()
    print(f"  [OK] Added {len(erp_vendors)} ERP vendors")
    
    # --- Get all vendor IDs for PO creation ---
    all_vendors = db.query(models.Vendor).all()
    vendor_ids = [v.id for v in all_vendors]
    
    # --- Purchase Orders ---
    pos = []
    po_data = [
        ("PO-2024-1001", vendor_ids[0 % len(vendor_ids)], 150000.00, 100, 1500.00, "confirmed_by_owner"),
        ("PO-2024-1002", vendor_ids[1 % len(vendor_ids)], 85000.00, 50, 1700.00, "confirmed_by_owner"),
        ("PO-2024-1003", vendor_ids[2 % len(vendor_ids)], 220000.00, 200, 1100.00, "confirmed_by_owner"),
        ("PO-2024-1004", vendor_ids[3 % len(vendor_ids)], 45000.00, 30, 1500.00, "confirmed_by_owner"),
        ("PO-2024-1005", vendor_ids[4 % len(vendor_ids)], 190000.00, 150, 1266.67, "confirmed_by_owner"),
        ("PO-2024-1006", vendor_ids[5 % len(vendor_ids)], 72000.00, 80, 900.00, "confirmed_by_owner"),
        ("PO-2024-1007", vendor_ids[0 % len(vendor_ids)], 310000.00, 250, 1240.00, "confirmed_by_owner"),
        ("PO-2024-1008", vendor_ids[1 % len(vendor_ids)], 58000.00, 40, 1450.00, "open"),
        ("PO-2024-1009", vendor_ids[2 % len(vendor_ids)], 125000.00, 100, 1250.00, "open"),
        ("PO-2024-1010", vendor_ids[3 % len(vendor_ids)], 96000.00, 60, 1600.00, "confirmed_by_owner"),
        ("PO-2024-1011", vendor_ids[6 % len(vendor_ids)], 175000.00, 120, 1458.33, "confirmed_by_owner"),
        ("PO-2024-1012", vendor_ids[7 % len(vendor_ids)], 64000.00, 45, 1422.22, "open"),
        ("PO-2024-1013", vendor_ids[8 % len(vendor_ids)], 280000.00, 200, 1400.00, "confirmed_by_owner"),
        ("PO-2024-1014", vendor_ids[9 % len(vendor_ids)], 41000.00, 25, 1640.00, "confirmed_by_owner"),
        ("PO-2024-1015", vendor_ids[10 % len(vendor_ids)], 138000.00, 90, 1533.33, "open"),
        ("PO-2024-1016", vendor_ids[11 % len(vendor_ids)], 205000.00, 170, 1205.88, "confirmed_by_owner"),
        ("PO-2024-1017", vendor_ids[4 % len(vendor_ids)], 92000.00, 70, 1314.29, "confirmed_by_owner"),
        ("PO-2024-1018", vendor_ids[5 % len(vendor_ids)], 167000.00, 130, 1284.62, "open"),
        ("PO-2024-1019", vendor_ids[6 % len(vendor_ids)], 53000.00, 35, 1514.29, "confirmed_by_owner"),
        ("PO-2024-1020", vendor_ids[7 % len(vendor_ids)], 245000.00, 180, 1361.11, "confirmed_by_owner"),
    ]
    
    for i, (po_num, vid, total, qty, unit_p, status) in enumerate(po_data):
        po = models.PurchaseOrder(
            po_number=po_num,
            vendor_id=vid,
            item_id=1,  # Reference first inventory item
            quantity=qty,
            unit_price=unit_p,
            total_amount=total,
            status=status,
            approved_by_owner=True,
            created_at=datetime.datetime(2024, 1, 10 + i),
        )
        pos.append(po)
    
    db.add_all(pos)
    db.commit()
    print(f"  [OK] Created {len(pos)} purchase orders")
    
    # --- Goods Receipts (for confirmed POs) ---
    receipts = []
    for po in pos:
        if po.status == "confirmed_by_owner":
            receipt = models.GoodsReceipt(
                purchase_order_id=po.id,
                received_date=po.created_at + datetime.timedelta(days=5),
                received_quantity=po.quantity,
                received_amount=po.total_amount,
                notes=f"Full delivery for {po.po_number}",
            )
            receipts.append(receipt)
    
    db.add_all(receipts)
    db.commit()
    print(f"  [OK] Created {len(receipts)} goods receipts")
    
    # --- Default ERP Connection ---
    if db.query(models.ERPConnection).count() == 0:
        default_conn = models.ERPConnection(
            connection_name="Python Sample DB",
            erp_type="python_db",
            is_active=True,
            test_status="success",
            last_tested=datetime.datetime.utcnow(),
        )
        db.add(default_conn)
        db.commit()
        print("  [OK] Created default ERP connection (Python Sample DB)")


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
            print(f"Database already has {existing_vendors} vendors. Skipping base seed data.")
            # Still try to seed ERP data
            seed_erp_data(db)
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
        
        # 4. Seed ERP data (vendors, POs, receipts, default connection)
        seed_erp_data(db)
        
        print("\n[SUCCESS] Database initialization complete!")
        print(f"\nSummary:")
        print(f"  - Vendors: {db.query(models.Vendor).count()}")
        print(f"  - Vendor Aliases: {len(aliases)}")
        print(f"  - Inventory Items: {len(inventory_items)}")
        print(f"  - Low Stock Items: {low_stock_count}")
        print(f"  - Purchase Orders: {db.query(models.PurchaseOrder).count()}")
        print(f"  - Goods Receipts: {db.query(models.GoodsReceipt).count()}")
        print(f"  - ERP Connections: {db.query(models.ERPConnection).count()}")
        
    except Exception as e:
        print(f"\n[ERROR] Error during initialization: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
