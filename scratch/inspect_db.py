import sys
import sqlite3
import json

conn = sqlite3.connect(r"d:\Program\Projects\pdf-rag-summarizer\backend\storage\data\registry.db")
cursor = conn.cursor()

print("--- DOCUMENTS ---")
for row in cursor.execute("SELECT * FROM documents"):
    print(row)

print("\n--- DOCUMENT UNITS ---")
for row in cursor.execute("SELECT doc_id, unit_index, unit_kind, page_number, length(text_content), substr(text_content, 1, 200) FROM document_units"):
    print(row)

print("\n--- DOCUMENT SECTIONS ---")
for row in cursor.execute("SELECT * FROM document_sections"):
    print(row)
