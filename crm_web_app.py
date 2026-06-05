#!/usr/bin/env python3
"""Local Streamlit web app for the Pinnacle Outreach CRM.

Safety notes:
- This app never sends email.
- This app never deletes CRM data.
- This app never reads, writes, or modifies Gmail credential files.
- Gmail draft creation is available only after an explicit confirmation checkbox
  and a visible button click, and it delegates to crm_create_draft_for_lead.py.

Run locally:
    pip install streamlit pandas
    streamlit run crm_web_app.py
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DB_FILE = APP_DIR / "pinnacle_crm.db"
EXPORT_DIR = APP_DIR / "crm_exports"
CREATE_DRAFT_SCRIPT = APP_DIR / "crm_create_draft_for_lead.py"
EXPORT_SCRIPT = APP_DIR / "export_crm.py"

REQUIRED_TABLES = {"leads", "activities", "drafts"}
BLOCKED_DRAFT_STATUSES = {"Do not contact", "Won", "Lost"}
ALLOWED_STATUSES = [
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
]


# -----------------------------
# Database helpers
# -----------------------------


def connect_db(read_only: bool = False) -> sqlite3.Connection:
    """Open the CRM database with row access by column name."""
    if read_only:
        conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def database_ready() -> tuple[bool, str]:
    """Validate that the expected local SQLite database and tables exist."""
    if not DB_FILE.exists():
        return False, f"Database not found: {DB_FILE}"

    try:
        with connect_db(read_only=True) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
    except sqlite3.Error as exc:
        return False, f"Unable to open database: {exc}"

    missing = sorted(REQUIRED_TABLES - tables)
    if missing:
        return False, "Missing required table(s): " + ", ".join(missing)
    return True, "CRM database is ready."


def query_df(sql: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    """Run a read-only query and return a pandas DataFrame."""
    with connect_db(read_only=True) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    """Fetch a single row from the CRM database."""
    with connect_db(read_only=True) as conn:
        return conn.execute(sql, params).fetchone()


def run_local_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run an existing local CRM script and capture output for display."""
    return subprocess.run(
        [sys.executable, *args],
        cwd=APP_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def table_columns(table_name: str) -> set[str]:
    """Return column names for a CRM table so optional fields can be handled safely."""
    with connect_db(read_only=True) as conn:
        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def clean_text(value: str | None) -> str | None:
    """Normalize form text fields before saving to SQLite."""
    cleaned = (value or "").strip()
    return cleaned or None


MANUAL_LEAD_ACTIVITY_MESSAGE = "Lead manually added from Streamlit CRM."


def record_manual_lead_activity_if_supported(
    conn: sqlite3.Connection,
    lead_id: int,
    created_at: str,
) -> bool:
    """Record the manual-add activity when the activities schema supports it."""
    activity_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(activities)").fetchall()
    }
    required_columns = {"lead_id", "activity_type", "created_at"}
    if not required_columns.issubset(activity_columns):
        return False

    values = {
        "lead_id": lead_id,
        "activity_type": "Lead manually added",
        "created_at": created_at,
    }
    if "notes" in activity_columns:
        values["notes"] = MANUAL_LEAD_ACTIVITY_MESSAGE
    else:
        values["activity_type"] = MANUAL_LEAD_ACTIVITY_MESSAGE
    if "metadata_json" in activity_columns:
        values["metadata_json"] = "{}"

    columns = list(values.keys())
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    conn.execute(
        f"INSERT INTO activities ({column_sql}) VALUES ({placeholders})",
        tuple(values[column] for column in columns),
    )
    return True


# -----------------------------
# CRM queries
# -----------------------------


def dashboard_counts() -> dict[str, int]:
    """Return top-line CRM metrics for the dashboard."""
    today_iso = date.today().isoformat()
    with connect_db(read_only=True) as conn:
        return {
            "total_leads": conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
            "total_activities": conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0],
            "total_drafts": conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0],
            "due_followups": conn.execute(
                """
                SELECT COUNT(*)
                FROM leads
                WHERE next_follow_up_at IS NOT NULL
                  AND TRIM(next_follow_up_at) != ''
                  AND DATE(next_follow_up_at) <= DATE(?)
                  AND status NOT IN ('Won', 'Lost', 'Do not contact')
                """,
                (today_iso,),
            ).fetchone()[0],
        }


def leads_by_status_df() -> pd.DataFrame:
    """Return lead counts grouped by status."""
    return query_df(
        """
        SELECT COALESCE(status, '(none)') AS status, COUNT(*) AS lead_count
        FROM leads
        GROUP BY COALESCE(status, '(none)')
        ORDER BY lead_count DESC, status ASC
        """
    )


def due_followups_df() -> pd.DataFrame:
    """Return leads with a due or past follow-up date."""
    return query_df(
        """
        SELECT id, company_name, contact_email, status, next_follow_up_at
        FROM leads
        WHERE next_follow_up_at IS NOT NULL
          AND TRIM(next_follow_up_at) != ''
          AND DATE(next_follow_up_at) <= DATE(?)
          AND status NOT IN ('Won', 'Lost', 'Do not contact')
        ORDER BY DATE(next_follow_up_at) ASC, id ASC
        """,
        (date.today().isoformat(),),
    )


def all_leads_df() -> pd.DataFrame:
    """Return a compact list of leads for selection controls."""
    return query_df(
        """
        SELECT id, company_name, contact_email, status, next_follow_up_at
        FROM leads
        ORDER BY company_name ASC, id ASC
        """
    )


def lead_detail(lead_id: int) -> sqlite3.Row | None:
    """Return all display fields for one lead."""
    return fetch_one(
        """
        SELECT id, company_name, industry, location, website, contact_email,
               contact_role, fit_score, fit_reason, status, source, created_at,
               updated_at, last_contact_at, next_follow_up_at, notes
        FROM leads
        WHERE id = ?
        """,
        (lead_id,),
    )


def activities_for_lead_df(lead_id: int) -> pd.DataFrame:
    """Return activities for one lead, newest first."""
    return query_df(
        """
        SELECT id, activity_type, notes, metadata_json, created_at
        FROM activities
        WHERE lead_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        """,
        (lead_id,),
    )


def drafts_for_lead_df(lead_id: int) -> pd.DataFrame:
    """Return Gmail draft records for one lead, newest first."""
    return query_df(
        """
        SELECT id, gmail_draft_id, recipient_email, subject, created_at
        FROM drafts
        WHERE lead_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        """,
        (lead_id,),
    )


# -----------------------------
# Safe write actions
# -----------------------------


def update_lead_status_and_followup(
    lead_id: int,
    old_status: str | None,
    new_status: str,
    old_next_follow_up_at: str | None,
    new_next_follow_up_at: str | None,
) -> None:
    """Update safe lead fields and record a CRM activity.

    This function never deletes data and never touches Gmail credentials. It only updates
    status / next_follow_up_at and inserts an audit activity row.
    """
    now_iso = datetime.now().isoformat()
    clean_followup = (new_next_follow_up_at or "").strip() or None

    with connect_db(read_only=False) as conn:
        conn.execute(
            """
            UPDATE leads
            SET status = ?, next_follow_up_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_status, clean_followup, now_iso, lead_id),
        )
        conn.execute(
            """
            INSERT INTO activities (lead_id, activity_type, notes, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                lead_id,
                "Lead updated in web app",
                (
                    f"old_status={old_status}; new_status={new_status}; "
                    f"old_next_follow_up_at={old_next_follow_up_at}; "
                    f"new_next_follow_up_at={clean_followup}"
                ),
                "{}",
                now_iso,
            ),
        )
        conn.commit()


def add_manual_lead(form_data: dict[str, str | None]) -> int:
    """Insert a manually entered lead and record an audit activity.

    This write path is intentionally limited to the existing CRM `leads` and
    `activities` tables. It never sends email, never creates Gmail drafts, and
    never reads or writes Gmail credential files.
    """
    lead_columns = table_columns("leads")
    now_iso = datetime.now().isoformat(timespec="seconds")

    values: dict[str, str | None] = {
        "company_name": clean_text(form_data.get("company_name")),
        "contact_email": clean_text(form_data.get("contact_email")),
        "status": "New lead",
    }

    optional_values = {
        "contact_role": clean_text(form_data.get("contact_role")),
        "industry": clean_text(form_data.get("industry")),
        "location": clean_text(form_data.get("location")),
        "next_follow_up_at": clean_text(form_data.get("next_follow_up_at")),
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    for column, value in optional_values.items():
        if column in lead_columns:
            values[column] = value

    missing_required_columns = [
        column for column in ("company_name", "contact_email", "status") if column not in lead_columns
    ]
    if missing_required_columns:
        raise sqlite3.Error(
            "Missing required leads column(s): " + ", ".join(missing_required_columns)
        )

    columns = list(values.keys())
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)

    with connect_db(read_only=False) as conn:
        cursor = conn.execute(
            f"INSERT INTO leads ({column_sql}) VALUES ({placeholders})",
            tuple(values[column] for column in columns),
        )
        lead_id = int(cursor.lastrowid)
        record_manual_lead_activity_if_supported(conn, lead_id, now_iso)
        conn.commit()

    return lead_id


# -----------------------------
# Streamlit pages
# -----------------------------


def show_add_lead() -> None:
    st.header("Add Lead")
    st.caption("Manually add one CRM lead. This page does not send emails or create Gmail drafts.")

    try:
        lead_columns = table_columns("leads")
    except sqlite3.Error as exc:
        st.error(f"Unable to inspect leads table: {exc}")
        return

    with st.form("add-lead-form", clear_on_submit=False):
        company_name = st.text_input("company_name *")
        contact_email = st.text_input("contact_email *")
        contact_role = st.text_input("contact_role")
        industry = st.text_input("industry")
        location = st.text_input("location")
        follow_up_date = st.date_input("next_follow_up_at", value=None)
        submitted = st.form_submit_button("Save new lead")

    if not submitted:
        return

    if not clean_text(company_name) or not clean_text(contact_email):
        st.error("company_name and contact_email are required.")
        return

    missing_optional_columns = sorted(
        {"contact_role", "industry", "location", "next_follow_up_at"} - lead_columns
    )
    if missing_optional_columns:
        st.warning(
            "Skipping optional field(s) missing from the leads table: "
            + ", ".join(missing_optional_columns)
        )

    form_data = {
        "company_name": company_name,
        "contact_email": contact_email,
        "contact_role": contact_role,
        "industry": industry,
        "location": location,
        "next_follow_up_at": follow_up_date.isoformat() if follow_up_date else None,
    }

    try:
        new_lead_id = add_manual_lead(form_data)
    except sqlite3.IntegrityError as exc:
        st.error(f"Could not add lead because the database rejected it: {exc}")
    except sqlite3.Error as exc:
        st.error(f"Could not add lead: {exc}")
    else:
        st.success(f"Lead saved successfully with id {new_lead_id}.")


def show_dashboard() -> None:
    st.header("Dashboard")
    counts = dashboard_counts()
    metric_cols = st.columns(5)
    metric_cols[0].metric("Total leads", counts["total_leads"])
    metric_cols[1].metric("Total activities", counts["total_activities"])
    metric_cols[2].metric("Total drafts", counts["total_drafts"])
    metric_cols[3].metric("Due follow-ups", counts["due_followups"])
    metric_cols[4].metric("Database", DB_FILE.name)

    st.subheader("Leads by status")
    status_df = leads_by_status_df()
    st.dataframe(status_df, use_container_width=True, hide_index=True)
    if not status_df.empty:
        st.bar_chart(status_df.set_index("status"))


def show_review_queue() -> None:
    st.header("Review Queue")
    st.caption("Shows leads with due or past follow-up dates. No Gmail action happens without a visible button click.")

    due_df = due_followups_df()
    st.dataframe(due_df, use_container_width=True, hide_index=True)

    if due_df.empty:
        st.info("No leads are due or past follow-up today.")
        return

    options = {
        f"#{row.id} — {row.company_name} ({row.contact_email or 'no email'})": int(row.id)
        for row in due_df.itertuples(index=False)
    }
    selected_label = st.selectbox("Select one lead for draft actions", list(options.keys()))
    selected_lead_id = options[selected_label]
    lead = lead_detail(selected_lead_id)

    if lead is None:
        st.error("Selected lead was not found.")
        return

    if lead["status"] in BLOCKED_DRAFT_STATUSES:
        st.warning(f"Draft creation is blocked for status: {lead['status']}")
    if not str(lead["contact_email"] or "").strip():
        st.warning("Draft creation is blocked because this lead has no contact email.")

    st.subheader("Draft controls")
    preview_col, create_col = st.columns(2)

    with preview_col:
        if st.button("Preview draft action", key=f"preview-{selected_lead_id}"):
            result = run_local_script([str(CREATE_DRAFT_SCRIPT), "--lead-id", str(selected_lead_id)])
            if result.returncode == 0:
                st.success("Preview completed. No draft was created.")
            else:
                st.error("Preview failed. No draft was created.")
            st.code((result.stdout + result.stderr).strip() or "(no output)")

    with create_col:
        confirmed = st.checkbox(
            "I confirm: create exactly one Gmail draft for this selected lead.",
            key=f"confirm-draft-{selected_lead_id}",
        )
        blocked = lead["status"] in BLOCKED_DRAFT_STATUSES or not str(lead["contact_email"] or "").strip()
        if st.button(
            "Create exactly one Gmail draft",
            key=f"create-draft-{selected_lead_id}",
            disabled=blocked or not confirmed,
        ):
            # Safety: one button click maps to exactly one invocation of the existing controlled script.
            result = run_local_script(
                [str(CREATE_DRAFT_SCRIPT), "--lead-id", str(selected_lead_id), "--apply"]
            )
            if result.returncode == 0:
                st.success("Created exactly one Gmail draft and recorded it in the CRM.")
            else:
                st.error("Draft creation failed or was blocked by the controlled script.")
            st.code((result.stdout + result.stderr).strip() or "(no output)")


def show_lead_detail() -> None:
    st.header("Lead Detail")
    leads = all_leads_df()
    if leads.empty:
        st.info("No leads found.")
        return

    options = {
        f"#{row.id} — {row.company_name} ({row.status})": int(row.id)
        for row in leads.itertuples(index=False)
    }
    selected_label = st.selectbox("Select a lead", list(options.keys()))
    selected_lead_id = options[selected_label]
    lead = lead_detail(selected_lead_id)

    if lead is None:
        st.error("Selected lead was not found.")
        return

    st.subheader("Lead fields")
    lead_fields = pd.DataFrame([dict(lead)])
    st.dataframe(lead_fields, use_container_width=True, hide_index=True)

    st.subheader("Update lead")
    current_status = lead["status"] if lead["status"] in ALLOWED_STATUSES else ALLOWED_STATUSES[0]
    new_status = st.selectbox(
        "Status",
        ALLOWED_STATUSES,
        index=ALLOWED_STATUSES.index(current_status),
    )
    new_followup = st.text_input(
        "next_follow_up_at (YYYY-MM-DD or ISO timestamp; leave blank to clear)",
        value=lead["next_follow_up_at"] or "",
    )

    if st.button("Save lead updates"):
        update_lead_status_and_followup(
            lead_id=selected_lead_id,
            old_status=lead["status"],
            new_status=new_status,
            old_next_follow_up_at=lead["next_follow_up_at"],
            new_next_follow_up_at=new_followup,
        )
        st.success("Lead updated and activity recorded.")
        st.rerun()

    st.subheader("Activities")
    st.dataframe(activities_for_lead_df(selected_lead_id), use_container_width=True, hide_index=True)

    st.subheader("Drafts")
    st.dataframe(drafts_for_lead_df(selected_lead_id), use_container_width=True, hide_index=True)


def show_exports() -> None:
    st.header("Exports")
    st.caption("Runs the existing export_crm.py script and shows exported CSV paths.")

    if st.button("Run CRM export"):
        result = run_local_script([str(EXPORT_SCRIPT)])
        if result.returncode == 0:
            st.success("Export completed.")
        else:
            st.error("Export failed.")
        st.code((result.stdout + result.stderr).strip() or "(no output)")

    st.subheader("Exported CSV files")
    if EXPORT_DIR.exists():
        csv_files = sorted(EXPORT_DIR.glob("*.csv"))
        if csv_files:
            for csv_file in csv_files:
                st.write(f"{csv_file}")
        else:
            st.info(f"No CSV files found in {EXPORT_DIR} yet.")
    else:
        st.info(f"Export directory does not exist yet: {EXPORT_DIR}")


def main() -> None:
    st.set_page_config(page_title="Pinnacle Outreach CRM", layout="wide")
    st.title("Pinnacle Outreach CRM v1")

    st.sidebar.header("Run locally")
    st.sidebar.code("pip install streamlit pandas\nstreamlit run crm_web_app.py")
    st.sidebar.header("Safety")
    st.sidebar.write("Never sends email.")
    st.sidebar.write("Never deletes data.")
    st.sidebar.write("Never modifies Gmail credentials.")
    st.sidebar.write("Draft creation requires confirmation and a button click.")

    ready, message = database_ready()
    if not ready:
        st.error(message)
        st.info(f"Place pinnacle_crm.db next to crm_web_app.py: {DB_FILE}")
        return

    st.sidebar.success(message)
    page = st.sidebar.radio(
        "Page",
        ["Dashboard", "Review Queue", "Lead Detail", "Add Lead", "Exports"],
    )

    if page == "Dashboard":
        show_dashboard()
    elif page == "Review Queue":
        show_review_queue()
    elif page == "Lead Detail":
        show_lead_detail()
    elif page == "Add Lead":
        show_add_lead()
    elif page == "Exports":
        show_exports()


if __name__ == "__main__":
    main()
