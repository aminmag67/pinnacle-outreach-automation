#!/usr/bin/env python3
import csv
import os
import sqlite3
import sys

DB_FILE = "pinnacle_crm.db"
EXPORT_DIR = "crm_exports"

TABLES = {
    "leads": "leads.csv",
    "activities": "activities.csv",
    "drafts": "drafts.csv",
}


def table_exists(conn, table_name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def export_table(conn, table_name, output_path):
    cur = conn.execute(f"SELECT * FROM {table_name}")
    headers = [description[0] for description in cur.description]
    rows = cur.fetchall()

    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        writer.writerows(rows)

    return len(rows)


def main():
    if not os.path.exists(DB_FILE):
        print(f"Error: Database file '{DB_FILE}' does not exist. Nothing to export.")
        sys.exit(1)

    try:
        with sqlite3.connect(DB_FILE) as conn:
            missing_tables = [table for table in TABLES if not table_exists(conn, table)]
            if missing_tables:
                print(f"Error: Missing required CRM tables: {', '.join(missing_tables)}")
                sys.exit(1)

            os.makedirs(EXPORT_DIR, exist_ok=True)

            for table_name, filename in TABLES.items():
                output_path = os.path.join(EXPORT_DIR, filename)
                count = export_table(conn, table_name, output_path)
                print(f"exported {table_name}: {count}")

    except sqlite3.Error as exc:
        print(f"Error: Could not export CRM data: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
