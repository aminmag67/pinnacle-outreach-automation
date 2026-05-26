#!/usr/bin/env python3
import os
import sqlite3
import sys

DB_FILE = "pinnacle_crm.db"

STATUSES_TO_REPORT = [
    "New lead",
    "Draft created",
    "Follow up needed",
    "Responded",
    "Call booked",
]

REQUIRED_TABLES = ["leads", "activities"]


def table_exists(conn, table_name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def get_latest_activities(conn, lead_id, limit=3):
    return conn.execute(
        """
        SELECT activity_type, notes, created_at
        FROM activities
        WHERE lead_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (lead_id, limit),
    ).fetchall()


def print_lead(conn, lead):
    (
        lead_id,
        company_name,
        contact_email,
        status,
        created_at,
        updated_at,
        last_contact_at,
        next_follow_up_at,
    ) = lead

    print(f"  Lead ID: {lead_id}")
    print(f"  Company: {company_name}")
    print(f"  Contact email: {contact_email or '(none)'}")
    print(f"  Status: {status}")
    print(f"  Created: {created_at}")
    print(f"  Updated: {updated_at}")
    print(f"  Last contact: {last_contact_at or '(none)'}")
    print(f"  Next follow-up: {next_follow_up_at or '(none)'}")

    activities = get_latest_activities(conn, lead_id)
    print("  Latest activities:")

    if not activities:
        print("    (none)")
    else:
        for activity_type, notes, created_at in activities:
            notes_text = f" | {notes}" if notes else ""
            print(f"    - {created_at}: {activity_type}{notes_text}")

    print()


def main():
    if not os.path.exists(DB_FILE):
        print(f"Error: Database file '{DB_FILE}' does not exist.")
        sys.exit(1)

    try:
        with sqlite3.connect(DB_FILE) as conn:
            missing_tables = [table for table in REQUIRED_TABLES if not table_exists(conn, table)]
            if missing_tables:
                print(f"Error: Missing required CRM tables: {', '.join(missing_tables)}")
                sys.exit(1)

            print("CRM Follow-up Report")
            print("====================")
            print()

            for status in STATUSES_TO_REPORT:
                leads = conn.execute(
                    """
                    SELECT
                        id,
                        company_name,
                        contact_email,
                        status,
                        created_at,
                        updated_at,
                        last_contact_at,
                        next_follow_up_at
                    FROM leads
                    WHERE status = ?
                    ORDER BY updated_at DESC, id DESC
                    """,
                    (status,),
                ).fetchall()

                print(f"{status}")
                print("-" * len(status))

                if not leads:
                    print("  (none)")
                    print()
                    continue

                for lead in leads:
                    print_lead(conn, lead)

    except sqlite3.Error as exc:
        print(f"Error: Could not read CRM data: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
