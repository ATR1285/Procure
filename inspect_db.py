import sqlite3

conn = sqlite3.connect("procure_iq.db")
cur  = conn.cursor()

# Delete the re-added false positives (ids 2 and 3)
cur.execute("DELETE FROM gmail_invoices WHERE id IN (2, 3)")
print(f"Deleted {cur.rowcount} rows from gmail_invoices")
conn.commit()

# Verify
cur.execute("SELECT id, subject, vendor_name, confidence FROM gmail_invoices ORDER BY id")
rows = cur.fetchall()
print(f"\ngmail_invoices now ({len(rows)} rows):")
for r in rows:
    subj   = (r[1] or "")[:70].encode("ascii", "replace").decode()
    vendor = (r[2] or "")[:40].encode("ascii", "replace").decode()
    print(f"  id={r[0]} conf={r[3]} vendor={vendor} | {subj}")

conn.close()
print("\nDone.")
