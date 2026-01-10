import sqlite3
import os
from datetime import datetime

db_path = 'stockpilot.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure the table exists (in case it wasn't created yet)
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS reorder_alerts
                   (
                       product_name
                       TEXT,
                       variant_title
                       TEXT,
                       inventory_quantity
                       INTEGER,
                       alert_date
                       TEXT
                   )
                   ''')

    # Insert a sample reorder alert
    test_alert = (
        'Sample Product A',
        'Large, Blue',
        5,  # low inventory quantity
        datetime.now().isoformat()
    )

    cursor.execute('''
                   INSERT INTO reorder_alerts (product_name, variant_title, inventory_quantity, alert_date)
                   VALUES (?, ?, ?, ?)
                   ''', test_alert)

    conn.commit()
    print("Test reorder alert added successfully.")
    conn.close()

except sqlite3.Error as e:
    print(f"SQLite error: {e}")
except Exception as e:
    print(f"An error occurred: {e}")