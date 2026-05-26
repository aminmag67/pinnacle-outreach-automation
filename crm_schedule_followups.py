#!/usr/bin/env python3
import argparse
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta

DB_FILE = "pinnacle_crm.db"
REQUIRED_TABLES = {"leads", "activities"}


def add_business_days(start_day: date, business_days: int) -> date:
    current = start_day
    added = 0

    while added < business_days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1

    return current


def load_leads(conn: sqlite3.Connection) -> list[tuple]:
    return conn.execute(
        """
        SELECT id, company_name, contact_email, status, next_follow_up_at
        FROM leads
        ORDER BY id ASC
        """
    ).fetchall()


def main() -> int:
    parser = argparse.ArgumentParser(description="Schedule CRM follow-ups for eligible leads")
    parser.add_argument("--apply", action="store_true", help="Apply updates to the database")
    args = parser.parse_args()

    if not os.path.exists(DB_FILE):
        print(f"Error: Database file '{DB_FILE}' does not exist.")
        return 1

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

            target_date = add_business_days(date.today(), 3).isoformat()
            leads = load_leads(conn)

            eligible = []
            skipped = []

            for lead_id, company_name, contact_email, status, next_follow_up_at in leads:
                if status != "New lead":
                    skipped.append((lead_id, company_name, "status_not_new_lead"))
                    continue

                if contact_email is None or str(contact_email).strip() == "":
                    skipped.append((lead_id, company_name, "missing_contact_email"))
                    continue

                if next_follow_up_at is not None and str(next_follow_up_at).strip() != "":
                    skipped.append((lead_id, company_name, "next_follow_up_already_set"))
                    continue

                eligible.append((lead_id, company_name, contact_email, target_date))

            print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
            print(f"Target next_follow_up_at: {target_date}")
            print(f"Total eligible leads: {len(eligible)}")
            print(f"Total skipped leads: {len(skipped)}")

            print("\nSkipped leads with reason:")
            if skipped:
                for lead_id, company_name, reason in skipped:
                    print(f"- lead_id={lead_id} | company={company_name} | reason={reason}")
            else:
                print("(none)")

            print("\nPlanned updates:")
            if eligible:
                for lead_id, company_name, contact_email, follow_date in eligible:
                    print(
                        f"- lead_id={lead_id} | company={company_name} | email={contact_email} | next_follow_up_at={follow_date}"
                    )
            else:
                print("(none)")

            if not args.apply:
                print("\nDry-run complete. No database changes were made.")
                return 0

            now_iso = datetime.now().isoformat()
            applied_count = 0

            for lead_id, company_name, contact_email, follow_date in eligible:
                conn.execute(
                    "UPDATE leads SET next_follow_up_at = ?, updated_at = ? WHERE id = ?",
                    (follow_date, now_iso, lead_id),
                )
                conn.execute(
                    """
                    INSERT INTO activities (lead_id, activity_type, notes, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        lead_id,
                        "Follow-up scheduled",
                        f"next_follow_up_at={follow_date}",
                        "{}",
                        now_iso,
                    ),
                )
                applied_count += 1

            conn.commit()
            print(f"\nApplied updates: {applied_count}")
            return 0

    except sqlite3.Error as exc:
        print(f"Error: Unable to process database '{DB_FILE}': {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
