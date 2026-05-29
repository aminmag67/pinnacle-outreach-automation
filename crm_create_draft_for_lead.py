#!/usr/bin/env python3
import argparse
import os
import sqlite3
import sys

from pinnacle_outreach_agent_utf8_fixed import (
    CRM_DB_FILE,
    create_gmail_draft,
    generate_outreach_email,
    record_activity,
    save_gmail_draft_record,
    update_lead_status,
)

REQUIRED_TABLES = {"leads", "activities", "drafts"}
BLOCKED_STATUSES = {"Do not contact", "Won", "Lost"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create one controlled Gmail draft for an existing CRM lead"
    )
    parser.add_argument("--lead-id", required=True, type=int, help="CRM lead ID to draft for")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create one real Gmail draft and record it in the CRM",
    )
    return parser.parse_args()


def is_blank(value: object) -> bool:
    return value is None or str(value).strip() == ""


def require_database_ready(conn: sqlite3.Connection) -> bool:
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    missing = sorted(REQUIRED_TABLES - tables)
    if missing:
        print("Error: Missing required table(s): " + ", ".join(missing))
        return False
    return True


def fetch_lead(conn: sqlite3.Connection, lead_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, company_name, industry, location, website, contact_email,
               contact_role, fit_score, fit_reason, status, source, created_at,
               updated_at, last_contact_at, next_follow_up_at, notes
        FROM leads
        WHERE id = ?
        """,
        (lead_id,),
    ).fetchone()


def print_selected_lead(lead: sqlite3.Row) -> None:
    print("Selected lead:")
    print(f"- id: {lead['id']}")
    print(f"- company_name: {lead['company_name']}")
    print(f"- contact_email: {lead['contact_email'] or '(none)'}")
    print(f"- status: {lead['status']}")
    print(f"- contact_role: {lead['contact_role'] or '(none)'}")
    print(f"- industry: {lead['industry'] or '(none)'}")
    print(f"- next_follow_up_at: {lead['next_follow_up_at'] or '(none)'}")


def lead_to_company(lead: sqlite3.Row) -> dict:
    return {
        "company_name": lead["company_name"],
        "industry": lead["industry"],
        "location": lead["location"],
        "website": lead["website"],
        "contact_email": lead["contact_email"],
        "contact_role": lead["contact_role"] or "Owner",
        "fit_score": lead["fit_score"],
        "fit_reason": lead["fit_reason"],
        "source": lead["source"] or "crm_create_draft_for_lead",
        "notes": lead["notes"],
        "pain_point": lead["fit_reason"] or "needs help creating consistent marketing content",
        "research": {
            "company_summary": lead["notes"] or "",
            "personalization_angle": lead["fit_reason"] or "",
            "suggested_offer": "monthly content package with short-form posts, email copy, and reusable marketing assets",
        },
    }


def validate_lead_can_draft(lead: sqlite3.Row) -> bool:
    if lead["status"] in BLOCKED_STATUSES:
        print(f"Error: Lead status '{lead['status']}' blocks draft creation.")
        return False

    if is_blank(lead["contact_email"]):
        print("Error: Lead is missing contact_email. Draft creation is blocked.")
        return False

    return True


def main() -> int:
    args = parse_args()

    if not os.path.exists(CRM_DB_FILE):
        print(f"Error: Database file '{CRM_DB_FILE}' does not exist.")
        return 1

    try:
        with sqlite3.connect(CRM_DB_FILE) as conn:
            conn.row_factory = sqlite3.Row

            if not require_database_ready(conn):
                return 1

            lead = fetch_lead(conn, args.lead_id)

    except sqlite3.Error as exc:
        print(f"Error: Unable to read database '{CRM_DB_FILE}': {exc}")
        return 1

    if lead is None:
        print(f"Error: Lead with id={args.lead_id} was not found.")
        return 1

    print_selected_lead(lead)

    if not validate_lead_can_draft(lead):
        return 1

    recipient_email = str(lead["contact_email"]).strip()

    print()
    print("Planned draft action:")
    print(f"- recipient_email: {recipient_email}")
    print("- action: create one Gmail draft from this CRM lead")

    if not args.apply:
        print()
        print("Mode: DRY-RUN")
        print("No Anthropic call, Gmail call, draft creation, or database write was performed.")
        return 0

    print()
    print("Mode: APPLY")
    print("Generating email for selected CRM lead...")

    email_data = generate_outreach_email(lead_to_company(lead))
    if not email_data:
        print("Error: Email generation failed. No Gmail draft was created.")
        return 1

    email_data["recipient_email"] = recipient_email

    print("Creating exactly one Gmail draft...")
    draft_id = create_gmail_draft(recipient_email, email_data)

    if not draft_id:
        print("Error: Gmail draft creation failed. CRM was not updated.")
        return 1

    save_gmail_draft_record(
        args.lead_id,
        draft_id,
        recipient_email,
        email_data.get("subject", ""),
        email_data.get("body", ""),
    )
    update_lead_status(args.lead_id, "Draft created")
    record_activity(args.lead_id, "Gmail draft created")

    print("Success: one Gmail draft was created and recorded in the CRM.")
    print(f"- lead_id: {args.lead_id}")
    print(f"- gmail_draft_id: {draft_id}")
    print("- new_status: Draft created")
    return 0


if __name__ == "__main__":
    sys.exit(main())