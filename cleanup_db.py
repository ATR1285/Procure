import sqlite3

conn = sqlite3.connect("procure_iq.db")
cur  = conn.cursor()

# Delete all gmail_invoices that lack a strong invoice keyword in subject
cur.execute("""
    DELETE FROM gmail_invoices WHERE
    LOWER(subject) NOT LIKE '%invoice%' AND
    LOWER(subject) NOT LIKE '%bill%' AND
    LOWER(subject) NOT LIKE '%receipt%' AND
    LOWER(subject) NOT LIKE '%amount due%' AND
    LOWER(subject) NOT LIKE '%purchase order%' AND
    LOWER(subject) NOT LIKE '%tax invoice%' AND
    LOWER(subject) NOT LIKE '%payment due%'
""")
print("gmail_invoices deleted:", cur.rowcount)
conn.commit()

cur.execute("SELECT id, subject, vendor_name, confidence FROM gmail_invoices ORDER BY id")
rows = cur.fetchall()
print(f"Remaining: {len(rows)}")
for r in rows:
    subj   = (r[1] or "")[:70].encode("ascii", "replace").decode()
    vendor = (r[2] or "")[:40].encode("ascii", "replace").decode()
    print(f"  id={r[0]} conf={r[3]} vendor={vendor} | {subj}")

conn.close()
print("Done.")
