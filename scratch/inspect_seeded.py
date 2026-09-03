import sqlite3

conn = sqlite3.connect('nodal_sentinel.db')
c = conn.cursor()

print("--- SEEDED EXCEPTIONS CREATION TIMESTAMPS ---")
rows = c.execute("SELECT created_at, count(*) FROM exceptions WHERE source_flag='seeded' GROUP BY created_at").fetchall()
for r in rows:
    print(r)

print("\n--- SEEDED EXCEPTIONS DETECTED_AT TIMESTAMPS ---")
rows = c.execute("SELECT detected_at, count(*) FROM exceptions WHERE source_flag='seeded' GROUP BY detected_at").fetchall()
for r in rows:
    print(r)

print("\n--- SEEDED EXCEPTIONS BY TYPE ---")
rows = c.execute("SELECT exception_type, severity, count(*) FROM exceptions WHERE source_flag='seeded' GROUP BY exception_type, severity").fetchall()
for r in rows:
    print(r)

print("\n--- ALL SEEDED EXCEPTION IDs (first 20 and last 20) ---")
all_ids = c.execute("SELECT id, exception_id, exception_type, primary_payment_id, exposure, created_at FROM exceptions WHERE source_flag='seeded' ORDER BY id").fetchall()
print("Total seeded exceptions:", len(all_ids))
print("First 10:")
for r in all_ids[:10]:
    print(" ", r)
print("Last 10:")
for r in all_ids[-10:]:
    print(" ", r)
