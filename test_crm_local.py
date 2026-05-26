#!/usr/bin/env python3
import sqlite3

from pinnacle_outreach_agent_utf8_fixed import init_crm, upsert_lead, record_activity

DB_FILE = "pinnacle_crm.db"


def main() -> None:
    init_crm()

    company = {
        "company_name": "Local CRM Validation Co",
        "industry": "local tech startups",
        "location": "Los Angeles, CA",
        "website": "https://example.com",
        "contact_role": "Head of Marketing",
        "fit_score": 8,
        "fit_reason": "Needs recurring content operations support",
        "source": "local_crm_validation",
        "notes": "SAFE_MODE local CRM validation",
    }

    lead_id = upsert_lead(company)

    record_activity(lead_id, "Email generated")
    record_activity(lead_id, "Draft skipped", notes="SAFE_MODE")

    with sqlite3.connect(DB_FILE) as conn:
        leads_count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        activities_count = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        drafts_count = conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0]
        latest_lead = conn.execute(
            "SELECT id, company_name, contact_email, status, source, created_at, updated_at "
            "FROM leads ORDER BY id DESC LIMIT 1"
        ).fetchone()
        latest_activities = conn.execute(
            "SELECT id, lead_id, activity_type, notes, created_at "
            "FROM activities ORDER BY id DESC LIMIT 10"
        ).fetchall()

    print(f"total leads: {leads_count}")
    print(f"total activities: {activities_count}")
    print(f"total drafts: {drafts_count}")
    print("latest lead row:")
    print(latest_lead)
    print("latest activity rows:")
    for row in latest_activities:
        print(row)
    print(f"drafts count is 0: {drafts_count == 0}")


if __name__ == "__main__":
    main()
