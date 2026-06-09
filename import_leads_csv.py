#!/usr/bin/env python3
"""Safely import leads from a CSV file into the local Pinnacle CRM.

Safety guarantees:
- Dry-run is the default unless --apply is explicitly used.
- Never sends email.
- Never creates Gmail drafts.
- Never reads or modifies Gmail credentials.

Expected CSV columns:
    company_name, contact_email, contact_role, industry, location, website, notes
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DB_FILE = Path(__file__).resolve().parent / "pinnacle_crm.db"
EXPECTED_COLUMNS = {
    "company_name",
    "contact_email",
    "contact_role",
    "industry",
    "location",
    "website",
    "notes",
}
REQUIRED_TABLES = {"leads"}


@dataclass
class LeadRow:
    row_number: int
    company_name: str
    contact_email: str
    contact_role: str
    industry: str
    location: str
    website: str
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import leads from CSV into pinnacle_crm.db")
    parser.add_argument("--file", required=True, help="Path to the lead CSV file")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate and preview without writes")
    mode.add_argument("--apply", action="store_true", help="Insert non-duplicate valid leads")
    return parser.parse_args()


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalize(value: str) -> str:
    return clean(value).casefold()


def read_csv_rows(csv_path: Path) -> tuple[list[LeadRow], int, int]:
    """Return valid rows, total data rows read, and invalid row count."""
    valid_rows: list[LeadRow] = []
    rows_read = 0
    invalid_rows = 0

    with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("CSV file is missing a header row.")

        fieldnames = {clean(name) for name in reader.fieldnames if name is not None}
        missing_columns = sorted(EXPECTED_COLUMNS - fieldnames)
        if missing_columns:
            raise ValueError("CSV is missing required column(s): " + ", ".join(missing_columns))

        for row_number, row in enumerate(reader, start=2):
            rows_read += 1
            company_name = clean(row.get("company_name"))
            if not company_name:
                invalid_rows += 1
                print(f"Invalid row {row_number}: company_name is required.")
                continue

            valid_rows.append(
                LeadRow(
                    row_number=row_number,
                    company_name=company_name,
                    contact_email=clean(row.get("contact_email")),
                    contact_role=clean(row.get("contact_role")),
                    industry=clean(row.get("industry")),
                    location=clean(row.get("location")),
                    website=clean(row.get("website")),
                    notes=clean(row.get("notes")),
                )
            )

    return valid_rows, rows_read, invalid_rows


def require_database_ready(conn: sqlite3.Connection) -> None:
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    missing = sorted(REQUIRED_TABLES - tables)
    if missing:
        raise sqlite3.Error("Missing required table(s): " + ", ".join(missing))

    lead_columns = {row[1] for row in conn.execute("PRAGMA table_info(leads)").fetchall()}
    required_columns = {
        "company_name",
        "contact_email",
        "contact_role",
        "industry",
        "location",
        "website",
        "notes",
        "status",
        "created_at",
        "updated_at",
    }
    missing_columns = sorted(required_columns - lead_columns)
    if missing_columns:
        raise sqlite3.Error("leads table is missing required column(s): " + ", ".join(missing_columns))


def existing_dedup_keys(
    conn: sqlite3.Connection,
) -> tuple[set[str], set[tuple[str, str]], set[tuple[str, str]]]:
    emails: set[str] = set()
    company_websites: set[tuple[str, str]] = set()
    company_locations: set[tuple[str, str]] = set()

    for company_name, contact_email, website, location in conn.execute(
        "SELECT company_name, contact_email, website, location FROM leads"
    ):
        company_key = normalize(company_name)
        email_key = normalize(contact_email)
        website_key = normalize(website)
        location_key = normalize(location)

        if email_key:
            emails.add(email_key)
        if website_key:
            company_websites.add((company_key, website_key))
        company_locations.add((company_key, location_key))

    return emails, company_websites, company_locations


def duplicate_reason(
    lead: LeadRow,
    keys: tuple[set[str], set[tuple[str, str]], set[tuple[str, str]]],
) -> str | None:
    emails, company_websites, company_locations = keys
    company_key = normalize(lead.company_name)
    email_key = normalize(lead.contact_email)
    website_key = normalize(lead.website)
    location_key = normalize(lead.location)

    if email_key and email_key in emails:
        return "same contact_email"
    if website_key and (company_key, website_key) in company_websites:
        return "same company_name plus website"
    if (company_key, location_key) in company_locations:
        return "same company_name plus location"
    return None


def add_dedup_keys(
    lead: LeadRow,
    keys: tuple[set[str], set[tuple[str, str]], set[tuple[str, str]]],
) -> None:
    emails, company_websites, company_locations = keys
    company_key = normalize(lead.company_name)
    email_key = normalize(lead.contact_email)
    website_key = normalize(lead.website)
    location_key = normalize(lead.location)

    if email_key:
        emails.add(email_key)
    if website_key:
        company_websites.add((company_key, website_key))
    company_locations.add((company_key, location_key))


def insert_lead(conn: sqlite3.Connection, lead: LeadRow) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    cursor = conn.execute(
        """
        INSERT INTO leads (
            company_name, contact_email, contact_role, industry, location,
            website, notes, status, source, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'New lead', 'csv_import', ?, ?)
        """,
        (
            lead.company_name,
            lead.contact_email or None,
            lead.contact_role or None,
            lead.industry or None,
            lead.location or None,
            lead.website or None,
            lead.notes or None,
            now,
            now,
        ),
    )
    return int(cursor.lastrowid)


def print_preview(lead: LeadRow, disposition: str) -> None:
    print(
        f"{disposition}: row={lead.row_number} | company={lead.company_name} | "
        f"email={lead.contact_email or '(blank)'} | website={lead.website or '(blank)'} | "
        f"location={lead.location or '(blank)'}"
    )


def main() -> int:
    args = parse_args()
    csv_path = Path(args.file).expanduser().resolve()
    mode = "APPLY" if args.apply else "DRY-RUN"

    print("Pinnacle CRM CSV Lead Import")
    print(f"Mode: {mode}")
    print(f"CSV file: {csv_path}")
    print("Safety: no emails will be sent; no Gmail drafts or credentials will be touched.")

    if not csv_path.is_file():
        print(f"Error: CSV file does not exist: {csv_path}", file=sys.stderr)
        return 1
    if not DB_FILE.is_file():
        print(f"Error: CRM database does not exist: {DB_FILE}", file=sys.stderr)
        return 1

    try:
        valid_rows, rows_read, invalid_rows = read_csv_rows(csv_path)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        print(f"Error: Unable to read CSV: {exc}", file=sys.stderr)
        return 1

    inserted = 0
    duplicates = 0
    try:
        with sqlite3.connect(DB_FILE) as conn:
            require_database_ready(conn)
            dedup_keys = existing_dedup_keys(conn)

            for lead in valid_rows:
                reason = duplicate_reason(lead, dedup_keys)
                if reason:
                    duplicates += 1
                    print_preview(lead, f"DUPLICATE SKIPPED ({reason})")
                    continue

                add_dedup_keys(lead, dedup_keys)
                if not args.apply:
                    print_preview(lead, "WOULD INSERT")
                    continue

                try:
                    lead_id = insert_lead(conn, lead)
                except sqlite3.IntegrityError as exc:
                    invalid_rows += 1
                    print(f"Invalid row {lead.row_number}: database rejected row: {exc}")
                    continue
                inserted += 1
                print(f"INSERTED: row={lead.row_number} | lead_id={lead_id} | company={lead.company_name}")

            if args.apply:
                conn.commit()

    except sqlite3.Error as exc:
        print(f"Error: CRM database operation failed: {exc}", file=sys.stderr)
        return 1

    print()
    print("Import summary")
    print(f"- rows read: {rows_read}")
    print(f"- rows inserted: {inserted}")
    print(f"- duplicates skipped: {duplicates}")
    print(f"- invalid rows skipped: {invalid_rows}")
    if not args.apply:
        print("- database writes: 0 (dry-run)")
    print("- emails sent: 0")
    print("- Gmail drafts created: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
