"""
Seed script: Generates 100+ realistic ERP-style inventory records.
Run: python seed_inventory.py
"""
import sys, os, random, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models import Base, InventoryItem

# Recreate tables
Base.metadata.create_all(bind=engine)

# ── Product catalog ────────────────────────────────────────────────────────
PRODUCTS = {
    "Electronics": [
        ("MacBook Pro 14-inch M3", "Apple", 1299, 1799),
        ("MacBook Air 13-inch M2", "Apple", 899, 1199),
        ("iPad Pro 12.9-inch", "Apple", 799, 1099),
        ("iPhone 15 Pro Max", "Apple", 999, 1199),
        ("ThinkPad X1 Carbon Gen 11", "Lenovo", 1049, 1399),
        ("ThinkPad T14s Gen 4", "Lenovo", 879, 1149),
        ("IdeaPad Slim 5", "Lenovo", 549, 729),
        ("XPS 15 9530", "Dell", 1199, 1599),
        ("Latitude 5540", "Dell", 899, 1199),
        ("Inspiron 16 Plus", "Dell", 699, 949),
        ("EliteBook 860 G10", "HP", 1149, 1529),
        ("ProBook 450 G10", "HP", 649, 879),
        ("ZBook Studio G10", "HP", 1599, 2149),
        ("Galaxy S24 Ultra", "Samsung", 899, 1199),
        ("Galaxy Tab S9 FE", "Samsung", 349, 449),
        ("ROG Zephyrus G14", "Asus", 1199, 1599),
        ("TUF Gaming F15", "Asus", 749, 999),
        ("ZenBook 14 OLED", "Asus", 799, 1049),
        ("Aspire 5 A515", "Acer", 449, 599),
        ("Predator Helios Neo 16", "Acer", 1099, 1449),
        ("PlayStation 5 Slim", "Sony", 399, 499),
        ("WH-1000XM5 Headphones", "Sony", 278, 398),
        ("Alpha A7 IV Camera", "Sony", 1998, 2498),
        ("Surface Pro 9", "Dell", 999, 1399),
        ("Chromebook Plus", "Acer", 349, 499),
        ("Vivobook Pro 16X OLED", "Asus", 1099, 1449),
    ],
    "Accessories": [
        ("MX Master 3S Mouse", "Logitech", 69, 99),
        ("MX Keys S Keyboard", "Logitech", 79, 109),
        ("C920 HD Pro Webcam", "Logitech", 49, 79),
        ("G Pro X Superlight 2", "Logitech", 109, 159),
        ("MX Anywhere 3S", "Logitech", 59, 79),
        ("Magic Keyboard with Touch ID", "Apple", 149, 199),
        ("Magic Mouse", "Apple", 69, 99),
        ("Magic Trackpad", "Apple", 99, 149),
        ("AirPods Pro 2nd Gen", "Apple", 179, 249),
        ("USB-C to HDMI Adapter", "Dell", 19, 34),
        ("Thunderbolt Dock WD22TB4", "Dell", 249, 339),
        ("Universal Laptop Stand", "HP", 29, 49),
        ("Bluetooth Travel Mouse", "HP", 19, 29),
        ("Galaxy Buds2 Pro", "Samsung", 149, 229),
        ("45W USB-C Charger", "Samsung", 29, 49),
        ("Type-C Hub 7-in-1", "Asus", 39, 59),
        ("ProArt Calibration Sensor", "Asus", 199, 279),
        ("65W GaN USB-C Charger", "Lenovo", 39, 59),
        ("Wireless Presenter R500s", "Logitech", 29, 49),
    ],
    "Office Equipment": [
        ("LaserJet Pro MFP M428fdw", "HP", 299, 449),
        ("OfficeJet Pro 9015e", "HP", 179, 279),
        ("Smart Tank 7602", "HP", 249, 349),
        ("EcoTank ET-4850", "Acer", 349, 499),
        ("B2236dw Laser Printer", "Lenovo", 149, 219),
        ("27-inch 4K Monitor S2722QC", "Dell", 279, 379),
        ("UltraSharp U3423WE 34-inch", "Dell", 799, 1099),
        ("ProDisplay XDR", "Apple", 3999, 4999),
        ("ViewFinity S9 5K Monitor", "Samsung", 1099, 1499),
        ("ProArt Display PA278QV", "Asus", 299, 429),
        ("Odyssey G7 32-inch", "Samsung", 449, 649),
        ("ThinkVision T27p-30", "Lenovo", 399, 549),
        ("27-inch QHD IPS Monitor", "Acer", 219, 329),
        ("Color LaserJet Enterprise", "HP", 599, 849),
    ],
    "Networking": [
        ("Catalyst 1000 24-Port Switch", "Cisco", 599, 849),
        ("Meraki MR46 Access Point", "Cisco", 799, 1149),
        ("Catalyst 9200L-48P Switch", "Cisco", 2499, 3499),
        ("ISR 1100 Router", "Cisco", 899, 1249),
        ("Webex Room Kit Mini", "Cisco", 1799, 2499),
        ("AX6000 WiFi 6 Router", "Asus", 249, 349),
        ("RT-AX86U Pro Router", "Asus", 199, 279),
        ("ZenWiFi AX Mesh System", "Asus", 349, 449),
        ("Nighthawk AX12 Router", "Acer", 299, 429),
        ("USB WiFi 6 Adapter", "Asus", 39, 59),
        ("Managed PoE Switch 16-Port", "Cisco", 449, 649),
    ],
    "Peripherals": [
        ("BRIO 4K Pro Webcam", "Logitech", 149, 219),
        ("Zone Vibe 100 Headset", "Logitech", 69, 99),
        ("Streamcam Plus", "Logitech", 119, 169),
        ("G915 TKL Wireless Keyboard", "Logitech", 179, 229),
        ("G435 Wireless Headset", "Logitech", 49, 79),
        ("Poly Voyager Focus 2", "HP", 199, 299),
        ("USB-C G5 Essential Dock", "HP", 149, 229),
        ("B600 Business Webcam", "Dell", 99, 149),
        ("WB5023 Webcam", "Dell", 79, 119),
        ("T7 Shield Portable SSD", "Samsung", 79, 119),
        ("Portable Monitor 15.6-inch", "Asus", 179, 259),
        ("INZONE H9 Wireless Headset", "Sony", 248, 348),
    ],
    "Storage Devices": [
        ("870 EVO 1TB SSD", "Samsung", 69, 99),
        ("990 PRO 2TB NVMe SSD", "Samsung", 149, 219),
        ("T7 Touch 2TB External SSD", "Samsung", 129, 189),
        ("980 PRO 1TB NVMe", "Samsung", 79, 119),
        ("IronWolf NAS 8TB HDD", "Acer", 179, 249),
        ("P50 Game Drive 2TB", "HP", 129, 179),
        ("Portable HDD 5TB", "Dell", 99, 139),
        ("PCIe 4.0 NVMe 2TB", "Asus", 139, 199),
        ("XD5 ME SSD 1.92TB Enterprise", "Dell", 299, 449),
        ("CFexpress Type B 256GB", "Sony", 349, 499),
        ("USB Flash Drive 256GB", "Samsung", 22, 34),
        ("MicroSD EVO Plus 512GB", "Samsung", 39, 54),
        ("Thunderbolt 4 NVMe Enclosure", "Asus", 79, 119),
        ("Enterprise SATA SSD 960GB", "Dell", 189, 279),
        ("Portable SSD 4TB", "HP", 199, 299),
        ("NVMe M.2 Gen5 1TB", "Samsung", 109, 169),
        ("USB-C Flash Drive 128GB", "Sony", 25, 39),
        ("CompactFlash 512GB", "Lenovo", 149, 229),
    ],
}

WAREHOUSES = ["WH-A1", "WH-B2", "WH-C3", "WH-D4"]
SUPPLIERS_MAP = {
    "Apple": "Apple Inc.",
    "Lenovo": "Lenovo Group Ltd.",
    "Dell": "Dell Technologies",
    "HP": "HP Inc.",
    "Logitech": "Logitech International",
    "Samsung": "Samsung Electronics",
    "Cisco": "Cisco Systems Inc.",
    "Asus": "ASUSTeK Computer Inc.",
    "Acer": "Acer Inc.",
    "Sony": "Sony Corporation",
}

CATEGORY_PREFIX = {
    "Electronics": "EL",
    "Accessories": "AC",
    "Office Equipment": "OF",
    "Networking": "NW",
    "Peripherals": "PR",
    "Storage Devices": "SD",
}


def seed():
    db = SessionLocal()

    # Clear existing
    db.query(InventoryItem).delete()
    db.commit()

    items = []
    counter = {}

    for category, products in PRODUCTS.items():
        prefix = CATEGORY_PREFIX[category]
        if prefix not in counter:
            counter[prefix] = 0

        for product_name, brand, cost_low, cost_high in products:
            counter[prefix] += 1
            sku = f"INV-{prefix}-{counter[prefix]:04d}"

            cost = round(random.uniform(cost_low * 0.9, cost_high * 0.7), 2)
            margin = random.uniform(0.15, 0.30)
            sell = round(cost * (1 + margin), 2)

            stock = random.randint(0, 500)
            reorder = random.randint(10, 50)

            if stock == 0:
                status = "Out of Stock"
            elif stock <= reorder:
                status = "Low Stock"
            else:
                status = "In Stock"

            item = InventoryItem(
                sku=sku,
                product_name=product_name,
                category=category,
                brand=brand,
                supplier=SUPPLIERS_MAP.get(brand, f"{brand} Corp."),
                stock_quantity=stock,
                reorder_level=reorder,
                reorder_quantity=random.choice([25, 50, 75, 100]),
                cost_price=cost,
                selling_price=sell,
                warehouse_location=random.choice(WAREHOUSES),
                last_updated=datetime.datetime.utcnow() - datetime.timedelta(
                    days=random.randint(0, 30),
                    hours=random.randint(0, 23)
                ),
                status=status,
            )
            items.append(item)

    db.add_all(items)
    db.commit()
    print(f"✓ Seeded {len(items)} inventory items")

    # Summary
    cats = {}
    for it in items:
        cats[it.category] = cats.get(it.category, 0) + 1
    for cat, count in sorted(cats.items()):
        print(f"  {cat}: {count} items")

    low = sum(1 for i in items if i.status == "Low Stock")
    oos = sum(1 for i in items if i.status == "Out of Stock")
    print(f"  Low Stock: {low}, Out of Stock: {oos}")
    db.close()


if __name__ == "__main__":
    seed()
