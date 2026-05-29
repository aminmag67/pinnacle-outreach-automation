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

def is_blank(value: object) -> bool:
return value is None or str(value).strip() == ""

def is_due_or_past(value: object, today_iso: str) -> bool:
if is_blank(value):
return False
return str(value).strip()[:10] <= today_iso

def fetch_leads(conn: sqlite3.Connection) -> list[tuple]:
return conn.execute(
"""
SELECT id, company_name, contact_email, status, next_follow_up_at
FROM leads
ORDER BY id ASC
"""
).fetchall()

def fetch_latest_activities(conn: sqlite3.Connection, lead_id: int, limit: int = 3) -> list[tuple]:
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

def has_later_followup_scheduled(conn: sqlite3.Connection, lead_id: int, activity_id: int, created_at: str) -> bool:
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

def review_reasons(
conn: sqlite3.Connection,
lead_id: int,
contact_email: str | None,
status: str | None,
next_follow_up_at: str | None,
latest_activities: list[tuple],
today_iso: str,
) -> list[str]:
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
def main() -> int:
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
        reason_counts: Counter[str] = Counter()

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
            print("\nNo leads currently need human review.")
            return 0

        print("\nReview queue:")
        for lead_id, company_name, contact_email, status, next_follow_up_at, reasons, activities in queued:
            print(
                f"\nLead {lead_id} | {company_name} | email={contact_email or '(none)'} | "
                f"status={status or '(none)'} | next_follow_up_at={next_follow_up_at or '(none)'}"
            )
            print("  Review reasons: " + ", ".join(reasons))
            if activities:
                print("  Latest activities:")
                for act_id, activity_type, notes, created_at in activities:
                    print(
                        f"    - activity_id={act_id} | type={activity_type} | "
                        f"notes={notes or '(none)'} | created_at={created_at}"
                    )
            else:
                print("  Latest activities: (none)")
except sqlite3.Error as exc:
    print(f"Error: Unable to read database '{DB_FILE}': {exc}")
    return 1

return 0
if name == "main":
sys.exit(main())