#!/usr/bin/env python3
import argparse
import os
import sqlite3
import sys
from datetime import datetime

DB_FILE = "pinnacle_crm.db"
REQUIRED_TABLES = {"leads", "activities"}


def table_names(conn):
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def fetch_lead(conn, lead_id):
    return conn.execute(
        """
        SELECT id, company_name, contact_email, status, last_contact_at, next_follow_up_at
        FROM leads
        WHERE id = ?
        """,
        (lead_id,),
    ).fetchone()


def main():
    parser = argparse.ArgumentParser(description="Mark a CRM lead email as sent manually")
    parser.add_argument("--lead-id", type=int, required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(DB_FILE):
        print(f"Error: Database file '{DB_FILE}' does not exist.")
        return 1

    try:
        with sqlite3.connect(DB_FILE) as conn:
            missing = sorted(REQUIRED_TABLES - table_names(conn))
            if missing:
                print("Error: Missing required table(s): " + ", ".join(missing))
                return 1

            lead = fetch_lead(conn, args.lead_id)
            if not lead:
                print(f"Error: Lead ID {args.lead_id} does not exist.")
                return 1

            lead_id, company_name, contact_email, status, last_contact_at, next_follow_up_at = lead

            print("Current lead")
            print("------------")
            print(f"id: {lead_id}")
            print(f"company_name: {company_name}")
            print(f"contact_email: {contact_email or '(none)'}")
            print(f"status: {status}")
            print(f"last_contact_at: {last_contact_at or '(none)'}")
            print(f"next_follow_up_at: {next_follow_up_at or '(none)'}")
            print()
            print("Planned change:")
            print("- status: Email sent")
            print("- last_contact_at: current timestamp")
            print("- next_follow_up_at: cleared")
            print("- activity: Email sent manually")

            if args.notes:
                print(f"- notes: {args.notes}")

            if not args.apply:
                print()
                print("DRY-RUN complete. No database changes were made.")
                return 0

            now_iso = datetime.now().isoformat()

            conn.execute(
                """
                UPDATE leads
                SET status = ?, last_contact_at = ?, updated_at = ?, next_follow_up_at = NULL
                WHERE id = ?
                """,
                ("Email sent", now_iso, now_iso, lead_id),
            )

            conn.execute(
                """
                INSERT INTO activities (lead_id, activity_type, notes, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    lead_id,
                    "Email sent manually",
                    args.notes,
                    "{}",
                    now_iso,
                ),
            )

            conn.commit()
            print()
            print(f"Updated lead {lead_id} to Email sent.")
            return 0

    except sqlite3.Error as exc:
        print(f"Error: Unable to update CRM database: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
