import sqlite3

conn = sqlite3.connect('nodal_sentinel.db')
c = conn.cursor()

print("--- EXCEPTIONS GROUPED BY SOURCE_FLAG ---")
for r in c.execute("SELECT source_flag, count(*) FROM exceptions GROUP BY source_flag").fetchall():
    print(r)

print("\n--- SAMPLE SEEDED (5) ---")
for r in c.execute("SELECT id, exception_id, exception_type, severity, exposure, primary_payment_id, source_flag, detected_at, created_at FROM exceptions WHERE source_flag='seeded' LIMIT 5").fetchall():
    print(r)

print("\n--- SAMPLE LIVE-INJECTED (5) ---")
for r in c.execute("SELECT id, exception_id, exception_type, severity, exposure, primary_payment_id, source_flag, detected_at, created_at FROM exceptions WHERE source_flag='live-injected' LIMIT 5").fetchall():
    print(r)

c.execute("PRAGMA table_info(injected_cases)")
cols = [row[1] for row in c.fetchall()]
print("\n--- INJECTED_CASES COLS ---", cols)

print("\n--- SAMPLE INJECTED_CASES (5) ---")
for r in c.execute(f"SELECT {', '.join(cols[:8])} FROM injected_cases LIMIT 5").fetchall():
    print(r)
