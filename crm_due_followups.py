#!/usr/bin/env python3
import os
import sqlite3
import sys
from datetime import date

DB_FILE = "pinnacle_crm.db"
REQUIRED_TABLES = {"leads", "activities"}
EXCLUDED_STATUSES = {"Won", "Lost", "Do not contact"}


def fetch_due_leads(conn: sqlite3.Connection, today_iso: str) -> list[tuple]:
    return conn.execute(
        """
        SELECT id, company_name, contact_email, status, next_follow_up_at
        FROM leads
        WHERE next_follow_up_at IS NOT NULL
          AND TRIM(next_follow_up_at) != ''
          AND DATE(next_follow_up_at) <= DATE(?)
          AND status NOT IN ('Won', 'Lost', 'Do not contact')
        ORDER BY DATE(next_follow_up_at) ASC, id ASC
        """,
        (today_iso,),
    ).fetchall()


def fetch_latest_activities(
    conn: sqlite3.Connection,
    lead_id: int,
    limit: int = 3,
) -> list[tuple]:
    return conn.execute(
        """
        SELECT id, activity_type, notes, created_at
        FROM activities
        WHERE lead_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (lead_id, limit),
    ).fetchall()


def main() -> int:
    if not os.path.exists(DB_FILE):
        print(f"Error: Database file '{DB_FILE}' does not exist.")
        return 1

    today_iso = date.today().isoformat()

    try:
        with sqlite3.connect(DB_FILE) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }

            missing = sorted(REQUIRED_TABLES - tables)
            if missing:
                print("Error: Missing required table(s): " + ", ".join(missing))
                return 1

            due_leads = fetch_due_leads(conn, today_iso)

            print(f"Due Follow-ups Report (today={today_iso})")
            print("=" * 80)

            if not due_leads:
                print("No leads are due for follow-up today or earlier.")
                return 0

            print(f"Total due leads: {len(due_leads)}")

            for lead_id, company_name, contact_email, status, next_follow_up_at in due_leads:
                print()
                print(f"Lead ID: {lead_id}")
                print(f"Company: {company_name}")
                print(f"Contact email: {contact_email or '(none)'}")
                print(f"Status: {status}")
                print(f"Next follow-up: {next_follow_up_at}")

                activities = fetch_latest_activities(conn, lead_id, limit=3)
                print("Latest activities:")

                if not activities:
                    print("  (none)")
                    continue

                for activity_id, activity_type, notes, created_at in activities:
                    notes_text = f" | {notes}" if notes else ""
                    print(f"  - {created_at}: {activity_type}{notes_text}")

            return 0

    except sqlite3.Error as exc:
        print(f"Error: Unable to read database '{DB_FILE}': {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
