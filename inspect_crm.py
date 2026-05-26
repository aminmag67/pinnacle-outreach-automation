#!/usr/bin/env python3
import sqlite3

DB_FILE = "pinnacle_crm.db"


def print_rows(title: str, rows: list[tuple]) -> None:
    print(title)
    if not rows:
        print("(none)")
        return
    for row in rows:
        print(row)


def main() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        leads_count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        activities_count = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        drafts_count = conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0]
        latest_leads = conn.execute(
            "SELECT id, company_name, status, contact_email, source, created_at, updated_at "
            "FROM leads ORDER BY id DESC LIMIT 10"
        ).fetchall()
        latest_activities = conn.execute(
            "SELECT id, lead_id, activity_type, notes, metadata_json, created_at "
            "FROM activities ORDER BY id DESC LIMIT 20"
        ).fetchall()
        latest_drafts = conn.execute(
            "SELECT id, lead_id, gmail_draft_id, recipient_email, subject, created_at "
            "FROM drafts ORDER BY id DESC LIMIT 10"
        ).fetchall()

    print(f"total leads: {leads_count}")
    print(f"total activities: {activities_count}")
    print(f"total drafts: {drafts_count}")
    print_rows("latest 10 leads:", latest_leads)
    print_rows("latest 20 activities:", latest_activities)
    print_rows("latest 10 drafts:", latest_drafts)


if __name__ == "__main__":
    main()
