import sqlite3
import json

conn = sqlite3.connect('nodal_sentinel.db')
c = conn.cursor()

flags = c.execute("SELECT source_flag, count(*) FROM exceptions GROUP BY source_flag").fetchall()
print("Flags in exceptions:", flags)

types = c.execute("SELECT exception_type, count(*) FROM exceptions GROUP BY exception_type").fetchall()
print("Types:", types)

print("\nSample seeded exceptions (first 10):")
for row in c.execute("SELECT exception_id, exception_type, severity, exposure, primary_payment_id, source_flag, created_at FROM exceptions WHERE source_flag='seeded' LIMIT 10").fetchall():
    print(" ", row)

print("\nSample live exceptions (first 10):")
for row in c.execute("SELECT exception_id, exception_type, severity, exposure, primary_payment_id, source_flag, created_at FROM exceptions WHERE source_flag='live-injected' LIMIT 10").fetchall():
    print(" ", row)

print("\nDataset metadata:")
for row in c.execute("SELECT * FROM dataset_metadata").fetchall():
    print(" ", row)

print("\nEvaluation ground truth:")
for row in c.execute("SELECT * FROM evaluation_ground_truth").fetchall():
    print(" ", row)

print("\nInjected cases table sample:")
for row in c.execute("SELECT id, case_id, anomaly_family, target_source, status, triggered_at FROM injected_cases LIMIT 10").fetchall():
    print(" ", row)
