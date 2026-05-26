#!/usr/bin/env python3
import argparse
import os
import sqlite3
import sys
from datetime import datetime

DB_FILE = "pinnacle_crm.db"

ALLOWED_STATUSES = {
    "New lead",
    "Draft created",
    "Email sent",
    "Responded",
    "Follow up needed",
    "Call booked",
    "Meeting completed",
    "Proposal sent",
    "Won",
    "Lost",
    "Do not contact",
}

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
        SELECT id, company_name, contact_email, status, next_follow_up_at
        FROM leads
        WHERE id = ?
        """,
        (lead_id,),
    ).fetchone()


def main():
    parser = argparse.ArgumentParser(description="Update one CRM lead status safely")
    parser.add_argument("--lead-id", type=int, required=True, help="Lead ID to update")
    parser.add_argument("--status", required=True, help="New lead status")
    parser.add_argument("--notes", default="", help="Optional notes for the status update activity")
    parser.add_argument("--apply", action="store_true", help="Apply the update")
    args = parser.parse_args()

    if args.status not in ALLOWED_STATUSES:
        print(f"Error: Unsupported status: {args.status}")
        print("Allowed statuses:")
        for status in sorted(ALLOWED_STATUSES):
            print(f"- {status}")
        return 1

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

            lead_id, company_name, contact_email, old_status, next_follow_up_at = lead

            print("Current lead")
            print("------------")
            print(f"id: {lead_id}")
            print(f"company_name: {company_name}")
            print(f"contact_email: {contact_email or '(none)'}")
            print(f"current status: {old_status}")
            print(f"next_follow_up_at: {next_follow_up_at or '(none)'}")
            print()

            print(f"Requested status change: {old_status} -> {args.status}")
            if args.status == "Do not contact":
                print("next_follow_up_at will be cleared.")

            if args.notes:
                print(f"notes: {args.notes}")

            if not args.apply:
                print()
                print("DRY-RUN complete. No database changes were made.")
                return 0

            now_iso = datetime.now().isoformat()
            new_next_follow_up_at = None if args.status == "Do not contact" else next_follow_up_at

            conn.execute(
                """
                UPDATE leads
                SET status = ?, updated_at = ?, next_follow_up_at = ?
                WHERE id = ?
                """,
                (args.status, now_iso, new_next_follow_up_at, lead_id),
            )

            activity_notes = f"old_status={old_status}; new_status={args.status}"
            if args.notes:
                activity_notes += f"; {args.notes}"

            conn.execute(
                """
                INSERT INTO activities (lead_id, activity_type, notes, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    lead_id,
                    "Status updated",
                    activity_notes,
                    "{}",
                    now_iso,
                ),
            )

            conn.commit()

            print()
            print(f"Updated lead {lead_id} status to {args.status}.")
            return 0

    except sqlite3.Error as exc:
        print(f"Error: Unable to update CRM database: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
