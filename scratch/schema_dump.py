import sqlite3

conn = sqlite3.connect(r"d:\Program\Projects\pdf-rag-summarizer\backend\storage\data\registry.db")
cursor = conn.cursor()

tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", tables)

for t in tables:
    name = t[0]
    print(f"\nSchema of {name}:")
    for col in cursor.execute(f"PRAGMA table_info({name})").fetchall():
        print(" ", col)
    rows = cursor.execute(f"SELECT * FROM {name} LIMIT 5").fetchall()
    print(f" Sample rows from {name} ({len(rows)}):")
    for r in rows:
        print("   ", r)
