#!/usr/bin/env python3
"""Discover local business leads from public web pages and add qualified leads to CRM.

Safety guarantees:
- Never sends email.
- Never creates Gmail drafts.
- Never reads or modifies Gmail credentials.
- Dry-run is the default unless --apply is explicitly provided.

Example:
    python discover_leads.py --industry "financial services" \
        --location "Ventura County CA" --limit 10 --dry-run
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse
from urllib.request import Request, urlopen


DB_FILE = Path(__file__).resolve().parent / "pinnacle_crm.db"
SEARCH_URLS = (
    "https://html.duckduckgo.com/html/?q={query}",
    "https://lite.duckduckgo.com/lite/?q={query}",
    "https://www.bing.com/search?q={query}",
)
USER_AGENT = "Mozilla/5.0 (compatible; PinnacleLeadResearch/1.0; local CRM research)"
REQUEST_TIMEOUT_SECONDS = 12
QUALIFIED_SCORE = 50
DRY_RUN_QUALIFIED_SCORE = 0
REQUIRED_TABLES = {"leads", "activities"}
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
IGNORED_EMAIL_SUFFIXES = ("@example.com", "@example.org", "@example.net")
IGNORED_HOSTS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "bing.com",
    "microsoft.com",
    "mapquest.com",
    "yelp.com",
    "yellowpages.com",
    "youtube.com",
}


@dataclass
class Lead:
    company_name: str
    website: str
    location: str
    industry: str
    contact_email: str
    source_url: str
    fit_score: int
    fit_reason: str


class PageParser(HTMLParser):
    """Collect a page title, visible text, links, and explicitly published emails."""

    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.emails: set[str] = set()
        self._link_href = ""
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "a":
            self._link_href = attrs_dict.get("href") or ""
            self._link_text = []
            if self._link_href.lower().startswith("mailto:"):
                address = self._link_href[7:].split("?", 1)[0]
                self.emails.update(extract_public_emails(unquote(address)))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "a" and self._link_href:
            self.links.append((self._link_href, clean_space(" ".join(self._link_text))))
            self._link_href = ""
            self._link_text = []

    def handle_data(self, data: str) -> None:
        cleaned = clean_space(data)
        if not cleaned:
            return
        self.text_parts.append(cleaned)
        if self.in_title:
            self.title_parts.append(cleaned)
        if self._link_href:
            self._link_text.append(cleaned)

    @property
    def title(self) -> str:
        return clean_space(" ".join(self.title_parts))

    @property
    def text(self) -> str:
        return clean_space(" ".join(self.text_parts))


class SearchParser(HTMLParser):
    """Collect external result links from DuckDuckGo's HTML search page."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[tuple[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            url = unwrap_search_url(self._href)
            title = clean_space(" ".join(self._text))
            if url and title and is_candidate_url(url):
                self.results.append((url, title))
            self._href = ""
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover and score local business leads")
    parser.add_argument("--industry", required=True, help="Target industry")
    parser.add_argument("--location", required=True, help="Target location")
    parser.add_argument("--limit", type=int, default=10, help="Maximum qualified leads to show or insert")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print leads without database writes")
    mode.add_argument("--apply", action="store_true", help="Insert qualified, non-duplicate leads")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print rejected candidates and rejection reasons",
    )
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 100:
        parser.error("--limit must be between 1 and 100")
    return args


def clean_space(value: str) -> str:
    return " ".join(html.unescape(value).split())


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            return ""
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read(1_500_000).decode(charset, errors="replace")


def unwrap_search_url(url: str) -> str:
    absolute = urljoin("https://html.duckduckgo.com", url)
    parsed = urlparse(absolute)
    redirect = parse_qs(parsed.query).get("uddg")
    return unquote(redirect[0]) if redirect else absolute


def normalized_host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host.removeprefix("www.")


def is_candidate_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = normalized_host(url)
    if not host or host.endswith("duckduckgo.com"):
        return False
    return not any(host == ignored or host.endswith(f".{ignored}") for ignored in IGNORED_HOSTS)


def canonical_website(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def extract_public_emails(text: str) -> set[str]:
    emails = {email.lower().rstrip(".,;:)") for email in EMAIL_RE.findall(text)}
    return {
        email
        for email in emails
        if not email.endswith(IGNORED_EMAIL_SUFFIXES)
        and not email.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
    }


def choose_public_email(parser: PageParser, page_html: str) -> str:
    emails = parser.emails | extract_public_emails(html.unescape(page_html))
    return sorted(emails)[0] if emails else ""


def company_name_from_title(page_title: str, search_title: str, website: str) -> str:
    title = page_title or search_title
    for separator in (" | ", " - ", " — ", " – ", " :: "):
        if separator in title:
            title = title.split(separator, 1)[0]
            break
    title = clean_space(title)
    if title:
        return title[:200]
    return normalized_host(website).split(".")[0].replace("-", " ").title()


def phrase_matches(text: str, phrase: str) -> bool:
    words = [word.lower() for word in re.findall(r"[A-Za-z0-9]+", phrase) if len(word) > 2]
    lowered = text.lower()
    return bool(words) and any(word in lowered for word in words)


def score_lead(page_text: str, industry: str, location: str, email: str) -> tuple[int, str]:
    score = 50  # A live company website found from the targeted web search.
    reasons = ["live business website found from targeted industry/location search"]
    if phrase_matches(page_text, industry):
        score += 20
        reasons.append("website references the target industry")
    if phrase_matches(page_text, location):
        score += 20
        reasons.append("website references the target location")
    if email:
        score += 10
        reasons.append("public contact email found")
    else:
        reasons.append("no public contact email found")
    return min(score, 100), "; ".join(reasons)


def contact_page_urls(parser: PageParser, website: str) -> list[str]:
    host = normalized_host(website)
    urls: list[str] = []
    for href, text in parser.links:
        candidate = urljoin(website, href)
        if normalized_host(candidate) != host:
            continue
        combined = f"{href} {text}".lower()
        if any(word in combined for word in ("contact", "about", "team")) and candidate not in urls:
            urls.append(candidate)
    return urls[:2]


def search_query_patterns(industry: str, location: str) -> list[str]:
    """Return broad search patterns so one empty result page does not stop discovery."""
    return [
        f"{industry} {location}",
        f"{industry} {location} contact",
        f"{industry} {location} email",
        f"{industry} near {location}",
        f"{industry} in {location}",
    ]


def debug_rejection(enabled: bool, candidate: str, reason: str) -> None:
    if enabled:
        print(f"DEBUG rejected: {candidate} | reason: {reason}", file=sys.stderr)


def discover(
    industry: str,
    location: str,
    limit: int,
    *,
    debug: bool = False,
) -> tuple[list[Lead], int]:
    raw_results: list[tuple[str, str]] = []
    for query_pattern in search_query_patterns(industry, location):
        print(f"Search query: {query_pattern}")
        encoded_query = quote_plus(query_pattern)
        query_results: list[tuple[str, str]] = []
        for search_url_template in SEARCH_URLS:
            search_url = search_url_template.format(query=encoded_query)
            print(f"Search URL: {search_url}")
            try:
                search_html = fetch_html(search_url)
            except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                debug_rejection(debug, search_url, f"search request failed: {exc}")
                print("Raw result links found: 0")
                continue

            search_parser = SearchParser()
            search_parser.feed(search_html)
            print(f"Raw result links found: {len(search_parser.results)}")
            query_results.extend(search_parser.results)
            if query_results:
                break
        raw_results.extend(query_results)

    print(f"Total raw result links found before scoring: {len(raw_results)}")

    leads: list[Lead] = []
    seen_hosts: set[str] = set()
    for result_url, result_title in raw_results:
        if len(leads) >= limit:
            break
        host = normalized_host(result_url)
        if not host:
            debug_rejection(debug, result_url, "missing hostname")
            continue
        if host in seen_hosts:
            debug_rejection(debug, result_url, f"duplicate result host: {host}")
            continue
        seen_hosts.add(host)

        try:
            page_html = fetch_html(result_url)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            debug_rejection(debug, result_url, f"unable to inspect page: {exc}")
            continue
        if not page_html:
            debug_rejection(debug, result_url, "page was not HTML or returned no readable HTML")
            continue

        page_parser = PageParser()
        page_parser.feed(page_html)
        website = canonical_website(result_url)
        email = choose_public_email(page_parser, page_html)

        if not email:
            for contact_url in contact_page_urls(page_parser, website):
                try:
                    contact_html = fetch_html(contact_url)
                except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                    debug_rejection(debug, contact_url, f"unable to inspect contact page: {exc}")
                    continue
                contact_parser = PageParser()
                contact_parser.feed(contact_html)
                email = choose_public_email(contact_parser, contact_html)
                if email:
                    break

        score, reason = score_lead(page_parser.text, industry, location, email)
        leads.append(
            Lead(
                company_name=company_name_from_title(page_parser.title, result_title, website),
                website=website,
                location=location,
                industry=industry,
                contact_email=email,
                source_url=result_url,
                fit_score=score,
                fit_reason=reason,
            )
        )
    return leads, len(raw_results)


def require_database_ready(conn: sqlite3.Connection) -> None:
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    missing = sorted(REQUIRED_TABLES - tables)
    if missing:
        raise sqlite3.Error("Missing required table(s): " + ", ".join(missing))


def existing_dedup_keys(conn: sqlite3.Connection) -> tuple[set[str], set[tuple[str, str]], set[str]]:
    websites: set[str] = set()
    company_locations: set[tuple[str, str]] = set()
    emails: set[str] = set()
    for company_name, location, website, contact_email in conn.execute(
        "SELECT company_name, location, website, contact_email FROM leads"
    ):
        if website:
            websites.add(normalized_host(str(website)))
        company_locations.add(((company_name or "").strip().lower(), (location or "").strip().lower()))
        if contact_email:
            emails.add(str(contact_email).strip().lower())
    return websites, company_locations, emails


def is_duplicate(lead: Lead, keys: tuple[set[str], set[tuple[str, str]], set[str]]) -> bool:
    websites, company_locations, emails = keys
    return (
        normalized_host(lead.website) in websites
        or (lead.company_name.strip().lower(), lead.location.strip().lower()) in company_locations
        or bool(lead.contact_email and lead.contact_email.strip().lower() in emails)
    )


def add_dedup_keys(lead: Lead, keys: tuple[set[str], set[tuple[str, str]], set[str]]) -> None:
    websites, company_locations, emails = keys
    websites.add(normalized_host(lead.website))
    company_locations.add((lead.company_name.strip().lower(), lead.location.strip().lower()))
    if lead.contact_email:
        emails.add(lead.contact_email.strip().lower())


def insert_lead(conn: sqlite3.Connection, lead: Lead) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    cursor = conn.execute(
        """
        INSERT INTO leads (
            company_name, industry, location, website, contact_email, fit_score,
            fit_reason, status, source, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'New lead', ?, ?, ?)
        """,
        (
            lead.company_name,
            lead.industry,
            lead.location,
            lead.website,
            lead.contact_email or None,
            lead.fit_score,
            lead.fit_reason,
            lead.source_url,
            now,
            now,
        ),
    )
    lead_id = int(cursor.lastrowid)
    conn.execute(
        """
        INSERT INTO activities (lead_id, activity_type, notes, metadata_json, created_at)
        VALUES (?, 'Lead discovered by web research', ?, ?, ?)
        """,
        (
            lead_id,
            f"source_url={lead.source_url}",
            json.dumps({"industry": lead.industry, "location": lead.location}),
            now,
        ),
    )
    return lead_id


def print_lead(lead: Lead, disposition: str) -> None:
    print()
    print(f"[{disposition}] {lead.company_name}")
    print(f"  website: {lead.website}")
    print(f"  location: {lead.location}")
    print(f"  industry: {lead.industry}")
    print(f"  contact_email: {lead.contact_email or '(none publicly found)'}")
    print(f"  source_url: {lead.source_url}")
    print(f"  fit_score: {lead.fit_score}")
    print(f"  fit_reason: {lead.fit_reason}")


def main() -> int:
    args = parse_args()
    mode = "APPLY" if args.apply else "DRY-RUN"
    print("Pinnacle CRM Web Lead Discovery")
    print(f"Mode: {mode}")
    print("Safety: no emails will be sent; no Gmail drafts or credentials will be touched.")
    print(f"Target: industry={args.industry!r}; location={args.location!r}; limit={args.limit}")

    if not DB_FILE.exists():
        print(f"Error: Database file does not exist: {DB_FILE}", file=sys.stderr)
        return 1

    try:
        with sqlite3.connect(DB_FILE) as conn:
            require_database_ready(conn)
            dedup_keys = existing_dedup_keys(conn)

            discovered, raw_result_count = discover(
                args.industry, args.location, args.limit * 3, debug=args.debug
            )
            qualification_threshold = QUALIFIED_SCORE if args.apply else DRY_RUN_QUALIFIED_SCORE
            print(f"Qualification threshold for {mode}: {qualification_threshold}")
            qualified = []
            for lead in discovered:
                if lead.fit_score >= qualification_threshold:
                    qualified.append(lead)
                else:
                    debug_rejection(
                        args.debug,
                        lead.source_url,
                        f"fit_score={lead.fit_score} below threshold={qualification_threshold}",
                    )
            candidates: list[Lead] = []
            duplicate_count = 0
            for lead in qualified:
                if is_duplicate(lead, dedup_keys):
                    duplicate_count += 1
                    if args.debug:
                        print_lead(lead, "REJECTED - DUPLICATE")
                        debug_rejection(args.debug, lead.source_url, "duplicate of CRM or run candidate")
                    continue
                candidates.append(lead)
                add_dedup_keys(lead, dedup_keys)
                disposition = "QUALIFIED" if args.apply else "POSSIBLE CANDIDATE"
                print_lead(lead, disposition)
                if len(candidates) >= args.limit:
                    break

            inserted = 0
            if args.apply:
                for lead in candidates:
                    try:
                        lead_id = insert_lead(conn, lead)
                    except sqlite3.IntegrityError as exc:
                        print(f"Warning: skipped insert for {lead.company_name}: {exc}", file=sys.stderr)
                        continue
                    inserted += 1
                    print(f"Inserted lead_id={lead_id}: {lead.company_name}")
                conn.commit()

    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"Error: Web search failed: {exc}", file=sys.stderr)
        return 1
    except sqlite3.Error as exc:
        print(f"Error: CRM database operation failed: {exc}", file=sys.stderr)
        return 1

    print()
    print("Safety summary")
    print(f"- raw result links: {raw_result_count}")
    print(f"- discovered leads: {len(discovered)}")
    print(f"- qualified leads: {len(qualified)}")
    print(f"- duplicates skipped: {duplicate_count}")
    print(f"- candidates shown: {len(candidates)}")
    print(f"- leads inserted: {inserted}")
    if not args.apply:
        print("- database writes: 0 (dry-run)")
    print("- emails sent: 0")
    print("- Gmail drafts created: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
