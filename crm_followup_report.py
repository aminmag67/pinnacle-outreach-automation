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

        print("CRM Follow-up Report")
        print("=" * 80)
        for status in REPORT_STATUSES:
            leads = fetch_leads_by_status(conn, status)
            print(f"\nStatus: {status} ({len(leads)} lead(s))")
            print("-" * 80)
            if not leads:
                print("  (none)")
                continue

            for lead in leads:
                lead_id, company_name, contact_email, lead_status, created_at, updated_at, last_contact_at, next_follow_up_at = lead
                print(
                    f"  Lead {lead_id} | {company_name} | email={contact_email or '(none)'} | status={lead_status}"
                )
                print(
                    f"    created_at={created_at} | updated_at={updated_at} | last_contact_at={last_contact_at or '(none)'} | next_follow_up_at={next_follow_up_at or '(none)'}"
                )

                activities = fetch_latest_activities(conn, lead_id, limit=3)
                if activities:
                    print("    Latest activities:")
                    for act_id, activity_type, notes, act_created_at in activities:
                        print(
                            f"      - activity_id={act_id} | type={activity_type} | notes={notes or '(none)'} | created_at={act_created_at}"
                        )
                else:
                    print("    Latest activities: (none)")
except sqlite3.Error as exc:
    print(f"Error: Unable to read database '{DB_FILE}': {exc}")
    return 1

return 0