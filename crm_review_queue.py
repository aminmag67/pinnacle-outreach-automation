#!/usr/bin/env python3
import os
import sqlite3
import sys
from collections import Counter
from datetime import date

DB_FILE = "pinnacle_crm.db"
REQUIRED_TABLES = {"leads", "activities"}

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

EXCLUDED_STATUSES = {"Won", "Lost", "Do not contact"}


def is_blank(value):
    return value is None or str(value).strip() == ""


def is_due_or_past(value, today_iso):
    if is_blank(value):
        return False
    return str(value).strip()[:10] <= today_iso


def fetch_leads(conn):
    return conn.execute(
        """
        SELECT id, company_name, contact_email, status, next_follow_up_at
        FROM leads
        ORDER BY id ASC
        """
    ).fetchall()


def fetch_latest_activities(conn, lead_id, limit=3):
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


def has_later_followup_scheduled(conn, lead_id, activity_id, created_at):
    row = conn.execute(
        """
        SELECT 1
        FROM activities
        WHERE lead_id = ?
          AND activity_type = 'Follow-up scheduled'
          AND (datetime(created_at) > datetime(?) OR (created_at = ? AND id > ?))
        LIMIT 1
        """,
        (lead_id, created_at, created_at, activity_id),
    ).fetchone()
    return row is not None


def review_reasons(conn, lead_id, contact_email, status, next_follow_up_at, latest_activities, today_iso):
    reasons = []
    latest_activity = latest_activities[0] if latest_activities else None

    if is_blank(contact_email):
        reasons.append("missing_contact_email")

    if status == "New lead" and is_blank(next_follow_up_at):
        reasons.append("new_lead_without_follow_up_date")

    if status == "New lead" and is_due_or_past(next_follow_up_at, today_iso):
        reasons.append("new_lead_due_or_past_follow_up")

    if status == "Follow up needed":
        reasons.append("status_follow_up_needed")

    if status == "Draft created":
        reasons.append("status_draft_created")

    if latest_activity and latest_activity[1] == "Draft skipped":
        reasons.append("latest_activity_draft_skipped")

    if latest_activity and latest_activity[1] == "Email generated":
        act_id, _activity_type, _notes, created_at = latest_activity
        if not has_later_followup_scheduled(conn, lead_id, act_id, created_at):
            reasons.append("email_generated_without_later_follow_up_scheduled")

    if status not in ALLOWED_STATUSES:
        reasons.append("invalid_status")

    return reasons


def main():
    if not os.path.exists(DB_FILE):
        print(f"Error: Database file '{DB_FILE}' does not exist.")
        return 1

    today_iso = date.today().isoformat()

    try:
        with sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True) as conn:
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

            leads = fetch_leads(conn)
            checked_count = 0
            queued = []
            reason_counts = Counter()

            for lead_id, company_name, contact_email, status, next_follow_up_at in leads:
                if status in EXCLUDED_STATUSES:
                    continue

                checked_count += 1
                latest_activities = fetch_latest_activities(conn, lead_id, limit=3)

                reasons = review_reasons(
                    conn,
                    lead_id,
                    contact_email,
                    status,
                    next_follow_up_at,
                    latest_activities,
                    today_iso,
                )

                if reasons:
                    queued.append(
                        (
                            lead_id,
                            company_name,
                            contact_email,
                            status,
                            next_follow_up_at,
                            reasons,
                            latest_activities,
                        )
                    )
                    reason_counts.update(reasons)

            print(f"CRM Review Queue (today={today_iso})")
            print("=" * 80)
            print(f"Total leads checked: {checked_count}")
            print(f"Total leads in review queue: {len(queued)}")
            print("Count by review reason:")

            if reason_counts:
                for reason, count in sorted(reason_counts.items()):
                    print(f"- {reason}: {count}")
            else:
                print("(none)")

            if not queued:
                print()
                print("No leads currently need human review.")
                return 0

            print()
            print("Review queue:")

            for lead_id, company_name, contact_email, status, next_follow_up_at, reasons, activities in queued:
                print()
                print(f"Lead ID: {lead_id}")
                print(f"Company: {company_name}")
                print(f"Contact email: {contact_email or '(none)'}")
                print(f"Status: {status or '(none)'}")
                print(f"Next follow-up: {next_follow_up_at or '(none)'}")
                print("Review reasons: " + ", ".join(reasons))
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