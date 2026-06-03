#!/usr/bin/env python3
import os
import sqlite3
import sys

DB_FILE = "pinnacle_crm.db"

REQUIRED_TABLES = {"leads", "activities", "drafts"}

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


def print_check(level, name, detail=""):
    suffix = f" - {detail}" if detail else ""
    print(f"[{level}] {name}{suffix}")


def table_names(conn):
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def count_rows(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def fetch_latest_activities(conn, limit=10):
    return conn.execute(
        """
        SELECT id, lead_id, activity_type, notes, created_at
        FROM activities
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def main():
    fail = False
    warn = False

    print("CRM Preproduction Safety Check")
    print("=" * 80)

    if not os.path.exists(DB_FILE):
        print_check("FAIL", "database exists", DB_FILE)
        print()
        print("Overall result: FAIL")
        print("Recommendation: Do not run real draft mode.")
        return 1

    print_check("PASS", "database exists", DB_FILE)

    try:
        with sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True) as conn:
            tables = table_names(conn)
            missing_tables = sorted(REQUIRED_TABLES - tables)

            if missing_tables:
                fail = True
                print_check("FAIL", "required tables exist", ", ".join(missing_tables))
                print()
                print("Overall result: FAIL")
                print("Recommendation: Do not run real draft mode.")
                return 1

            print_check("PASS", "required tables exist", ", ".join(sorted(REQUIRED_TABLES)))

            leads_count = count_rows(conn, "leads")
            activities_count = count_rows(conn, "activities")
            drafts_count = count_rows(conn, "drafts")

            print_check("PASS", "total leads", str(leads_count))
            print_check("PASS", "total activities", str(activities_count))

            if drafts_count > 0:
                warn = True
                print_check("WARN", "total drafts", f"{drafts_count} existing draft record(s)")
            else:
                print_check("PASS", "total drafts", str(drafts_count))

            missing_email_rows = conn.execute(
                """
                SELECT id, company_name
                FROM leads
                WHERE status = 'New lead'
                  AND (contact_email IS NULL OR TRIM(contact_email) = '')
                ORDER BY id ASC
                """
            ).fetchall()

            if missing_email_rows:
                fail = True
                print_check("FAIL", "New leads missing contact_email", str(len(missing_email_rows)))
                for lead_id, company_name in missing_email_rows:
                    print(f"  - lead_id={lead_id} | company={company_name}")
            else:
                print_check("PASS", "New leads missing contact_email", "0")

            invalid_status_rows = conn.execute(
                "SELECT id, company_name, status FROM leads ORDER BY id ASC"
            ).fetchall()

            invalid_statuses = [
                (lead_id, company_name, status)
                for lead_id, company_name, status in invalid_status_rows
                if status not in ALLOWED_STATUSES
            ]

            if invalid_statuses:
                fail = True
                print_check("FAIL", "leads with invalid status", str(len(invalid_statuses)))
                for lead_id, company_name, status in invalid_statuses:
                    print(f"  - lead_id={lead_id} | company={company_name} | status={status}")
            else:
                print_check("PASS", "leads with invalid status", "0")

            do_not_contact_rows = conn.execute(
                """
                SELECT id, company_name
                FROM leads
                WHERE status = 'Do not contact'
                ORDER BY id ASC
                """
            ).fetchall()

            if do_not_contact_rows:
                warn = True
                print_check("WARN", "leads marked Do not contact", str(len(do_not_contact_rows)))
                for lead_id, company_name in do_not_contact_rows:
                    print(f"  - lead_id={lead_id} | company={company_name}")
            else:
                print_check("PASS", "leads marked Do not contact", "0")

            followup_rows = conn.execute(
                """
                SELECT id, company_name, next_follow_up_at
                FROM leads
                WHERE next_follow_up_at IS NOT NULL
                  AND TRIM(next_follow_up_at) != ''
                ORDER BY next_follow_up_at ASC, id ASC
                """
            ).fetchall()

            if followup_rows:
                warn = True
                print_check("WARN", "leads with next_follow_up_at set", str(len(followup_rows)))
                for lead_id, company_name, next_follow_up_at in followup_rows:
                    print(f"  - lead_id={lead_id} | company={company_name} | next_follow_up_at={next_follow_up_at}")
            else:
                print_check("PASS", "leads with next_follow_up_at set", "0")

            print()
            print("Latest 10 activities")
            print("-" * 80)

            latest_activities = fetch_latest_activities(conn)
            if latest_activities:
                for activity_id, lead_id, activity_type, notes, created_at in latest_activities:
                    print(
                        f"- activity_id={activity_id} | lead_id={lead_id} | "
                        f"type={activity_type} | notes={notes or '(none)'} | created_at={created_at}"
                    )
            else:
                print("(none)")

    except sqlite3.Error as exc:
        print_check("FAIL", "database read", str(exc))
        print()
        print("Overall result: FAIL")
        print("Recommendation: Do not run real draft mode.")
        return 1

    print()

    if fail:
        print("Overall result: FAIL")
        print("Recommendation: Do not run real draft mode.")
        return 1

    if warn:
        print("Overall result: WARN")
        print("Recommendation: Review warnings before proceeding.")
        return 0

    print("Overall result: PASS")
    print("Recommendation: Safe to proceed to manual real-draft test, if approved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
