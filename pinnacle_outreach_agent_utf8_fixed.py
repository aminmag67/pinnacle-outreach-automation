#!/usr/bin/env python3
"""
Pinnacle Content Studio - Autonomous Outreach Agent
Generates company leads, researches them with Claude, creates personalized Gmail drafts,
and logs all activity to a tracking file.

LIVE VERSION: Gmail OAuth2 integration - creates REAL Gmail drafts
"""

import anthropic
import os
import time
import json
import random
import base64
import re
import argparse
from datetime import datetime, timedelta
from typing import Optional, Any
from email.message import EmailMessage


# ============================================================================
# CONFIGURATION
# ============================================================================

# Read API key from environment variable.
# In PowerShell, set it before running:
#   $env:ANTHROPIC_API_KEY="your_api_key_here"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
SAFE_MODE_DEFAULT = os.environ.get("SAFE_MODE", "true").strip().lower()
DRY_RUN_DEFAULT = os.environ.get("DRY_RUN", "false").strip().lower()

# LOCAL TARGETING - VENTURA & LA COUNTIES
TARGET_LOCATION = "Ventura County and Los Angeles County, California"
TARGET_COMPANY_SIZE = "small to mid-size (10-500 employees)"

INDUSTRIES = [
    "local marketing agencies",
    "regional training companies",
    "local tech startups",
    "independent consulting firms",
    "local ecommerce businesses",
    "regional SaaS companies",
    "local financial services",
    "healthcare practices and clinics",
    "private schools and education centers",
    "local manufacturing and production",
    "event management companies",
    "real estate agencies",
    "insurance agencies",
    "accounting firms",
    "interior design studios",
    "architectural firms",
    "law offices",
    "dental practices",
    "veterinary clinics",
    "fitness and wellness centers"
]

TARGET_ROLES = [
    "Head of Marketing",
    "VP of Training & Development",
    "Director of Content Strategy",
    "Chief Marketing Officer",
    "Learning & Development Manager",
    "Content Director",
    "Marketing Manager",
    "Training Director",
    "VP of Marketing",
    "Director of Learning & Development",
    "VP of Communications",
    "Chief Content Officer",
    "Director of Corporate Training",
    "Senior Marketing Manager",
    "Instructional Design Manager",
    "Head of Communications",
    "Director of Employee Development",
    "VP of HR & Training",
    "Chief Human Resources Officer",
    "VP of Human Resources",
    "Director of Human Resources",
    "HR Manager",
    "Talent Development Manager",
    "Head of Talent Management",
    "Director of Talent Acquisition",
    "VP of Talent & Organizational Development",
    "Chief People Officer",
    "Head of Employee Experience",
    "Director of Organizational Development",
    "Senior HR Manager",
    "HR Director",
    "Talent Strategy Manager",
    "Head of Culture & Engagement",
    "Operations Manager",
    "Business Manager",
    "Owner",
    "Executive Director"
]

CAMPAIGN_INTERVALS = {
    "research": 30,  # minutes between research cycles
    "daily_limit": 5,  # max emails per day
    "cooldown": 60   # minutes between emails to same company
}


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def validate_startup_requirements(*, safe_mode: bool, dry_run: bool) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY. Set it before running the agent.")

    if safe_mode or dry_run:
        print("Startup check: skipping Gmail credentials validation because no Gmail drafts will be created (SAFE_MODE or DRY_RUN is enabled).")
        return

    if not os.path.exists("credentials.json"):
        raise RuntimeError(
            "Missing credentials.json. Gmail OAuth credentials are required when SAFE_MODE=false and DRY_RUN=false."
        )


# ============================================================================
# COMPANY GENERATION & RESEARCH
# ============================================================================

def generate_company_targets(num_companies: int = 5) -> list[dict]:
    """
    Generate SMALL/MID-SIZE LOCAL companies in Ventura & LA counties
    that would benefit from Pinnacle Content Studio's services.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. In PowerShell, run: "
            '$env:ANTHROPIC_API_KEY="your_api_key_here"'
        )
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = f"""Generate {num_companies} realistic, SMALL TO MID-SIZE LOCAL businesses 
in {TARGET_LOCATION} that would benefit from Pinnacle Content Studio's services.

IMPORTANT CONSTRAINTS:
1. Company size: {TARGET_COMPANY_SIZE}
2. Location: Must be based in Ventura County or Los Angeles County, California
3. Type: Local/regional businesses - NOT national chains or enterprise companies
4. Budget: Small to moderate marketing budgets (not Fortune 500s)
5. Pain point: Struggling with content creation or marketing materials in-house

AVOID (these are too big):
- Salesforce, HubSpot, Deloitte, Accenture, major national brands
- Companies with 500+ employees
- Fortune 1000 companies
- Companies with dedicated in-house marketing teams

FOCUS ON (these are ideal targets):
- Local agencies, consulting firms, practices
- Growing businesses that need help scaling content
- Service-based companies (accounting, law, dental, real estate, etc.)
- Companies with 20-200 employees
- Businesses that outsource marketing needs

For each company, provide:
1. Company name (realistic LOCAL business, not made up)
2. Industry (from provided list)
3. Estimated size (startup/small/mid)
4. Location (city in Ventura or LA County)
5. Target contact role
6. Pain point Pinnacle can solve

Return as JSON array. Example:
[
  {{
    "company_name": "Westlake Marketing Group",
    "industry": "local marketing agencies",
    "size": "small",
    "location": "Westlake Village, CA",
    "contact_role": "Head of Marketing",
    "pain_point": "needs to create 4-6 pieces of content weekly for clients but lacking resources"
  }}
]

Think about LOCAL businesses in Ventura County (Thousand Oaks, Simi Valley, Oxnard, Port Hueneme, Camarillo, Ojai, etc.) 
and LA County (Santa Monica, Beverly Hills, Burbank, Santa Clarita, Torrance, Long Beach, Pasadena, etc.)"""

    message = client.messages.create(
        model="claude-opus-4-1",
        max_tokens=1500,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    try:
        response_text = message.content[0].text
        # Extract JSON from response
        start = response_text.find('[')
        end = response_text.rfind(']') + 1
        json_str = response_text[start:end]
        companies = json.loads(json_str)
        return companies
    except (json.JSONDecodeError, IndexError) as e:
        print(f"Error parsing company list: {e}")
        return []


def _get_anthropic_client() -> anthropic.Anthropic:
    """
    Create an Anthropic client after validating the API key.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. In PowerShell, run: "
            '$env:ANTHROPIC_API_KEY="your_api_key_here"'
        )
    return anthropic.Anthropic(api_key=api_key)


def _extract_json_object(text: str) -> Optional[dict[str, Any]]:
    """
    Extract the first JSON object from a Claude response.
    """
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start == -1 or end <= start:
            return None
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None


def _extract_claude_json_response(text: str) -> Optional[dict[str, Any]]:
    """
    Robustly extract JSON from Claude output by trying:
    1) Full-response JSON parse
    2) JSON fenced code blocks
    3) First JSON object within surrounding prose
    """
    if not text:
        return None

    # 1) Direct parse of full response
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 2) Parse ```json ... ``` fenced blocks
    fenced_matches = re.findall(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    for candidate in fenced_matches:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    # 3) Fallback to first JSON object in prose
    return _extract_json_object(text)

def research_company(company: dict) -> dict:
    """
    Add lightweight research context to a generated company target.

    This version uses Claude's general reasoning from the company target data.
    It does not claim to perform live web research unless you add a web-search tool.
    """
    client = _get_anthropic_client()

    company_name = company.get("company_name", "Unknown company")
    location = company.get("location", TARGET_LOCATION)
    industry = company.get("industry", "local business")
    contact_role = company.get("contact_role", random.choice(TARGET_ROLES))
    pain_point = company.get("pain_point", "needs help producing consistent marketing content")

    prompt = f"""Create a concise outreach research brief for this local prospect.

Company: {company_name}
Location: {location}
Industry: {industry}
Target role: {contact_role}
Known pain point: {pain_point}

Return only valid JSON with these fields:
{{
  "company_summary": "1 sentence summary",
  "likely_content_needs": ["need 1", "need 2", "need 3"],
  "personalization_angle": "specific angle for a cold email",
  "suggested_offer": "specific Pinnacle Content Studio offer",
  "confidence": "low, medium, or high"
}}

Important:
- Do not invent private facts, exact revenue, exact employee count, or named people.
- Keep it practical for a small or mid-size local business.
"""

    try:
        message = client.messages.create(
            model="claude-opus-4-1",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text
        research = _extract_json_object(response_text) or {}
    except Exception as e:
        print(f"  ⚠️  Research fallback used: {e}")
        research = {}

    company["research"] = {
        "company_summary": research.get(
            "company_summary",
            f"{company_name} is a {industry} business in {location}."
        ),
        "likely_content_needs": research.get(
            "likely_content_needs",
            [
                "consistent social content",
                "clear service-page copy",
                "email and follow-up materials",
            ],
        ),
        "personalization_angle": research.get(
            "personalization_angle",
            f"{company_name} may need steady content support without hiring a full-time content team."
        ),
        "suggested_offer": research.get(
            "suggested_offer",
            "monthly content package with short-form posts, email copy, and reusable marketing assets"
        ),
        "confidence": research.get("confidence", "medium"),
    }

    return company


def generate_outreach_email(company: dict) -> Optional[dict]:
    """
    Generate a personalized cold email draft for a researched company.
    """
    client = _get_anthropic_client()

    company_name = company.get("company_name", "your team")
    industry = company.get("industry", "local business")
    contact_role = company.get("contact_role", "Owner")
    pain_point = company.get("pain_point", "needs help creating consistent marketing content")
    research = company.get("research", {})

    prompt = f"""Write a concise cold outreach email for Pinnacle Content Studio.

Prospect:
- Company: {company_name}
- Industry: {industry}
- Target role: {contact_role}
- Pain point: {pain_point}
- Research summary: {research.get("company_summary", "")}
- Personalization angle: {research.get("personalization_angle", "")}
- Suggested offer: {research.get("suggested_offer", "")}

Pinnacle Content Studio helps small and mid-size local businesses create practical marketing content, including social posts, email copy, landing page copy, lead magnets, training content, and reusable content systems.

Return only this JSON object schema:
{{
  "subject": "string",
  "body": "string"
}}

Strict output rules:
- Return only valid JSON.
- Do not include markdown.
- Do not include ```json fences.
- Do not include any explanation text before or after JSON.
- Escape newlines inside JSON strings if needed.

Content rules:
- subject: under 9 words.
- body: 120 words max.
- Every email body must include one clear call to action to visit https://www.pinnaclecontentstudio.com.
- When the prospect appears to have a website or active online presence, offer a free branding report as an optional next step.
- Do not offer the free branding report when there is no sign the prospect has a website or online presence.
- Keep the call to action natural and low-pressure.
- Do not use em dashes or en dashes.
- Sound human and direct.
- Do not overpromise.
- Do not mention AI unless useful.
- Ask for a quick call or permission to send a few ideas.
- Do not include a signature. The script adds one.
"""

    try:
        message = client.messages.create(
            model="claude-opus-4-1",
            max_tokens=900,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text
        email_data = _extract_claude_json_response(response_text)
        if not email_data:
            preview = response_text[:200].replace("\n", " ")
            print(f"  ??  Claude response preview (first 200 chars): {preview}")
            raise ValueError("Claude did not return valid JSON.")

        required_fields = ["subject", "body"]
        missing_fields = [field for field in required_fields if not email_data.get(field)]
        if missing_fields:
            print(f"  ??  Missing required email fields: {', '.join(missing_fields)}")
            raise ValueError(f"Email JSON missing required fields: {', '.join(missing_fields)}")

        email_data.setdefault("company", company_name)
        email_data.setdefault("contact_role", contact_role)
        email_data.setdefault("industry", industry)
        return email_data

    except Exception as e:
        print(f"  ✗ Error generating email: {e}")
        return None


def clean_email_text(value: object) -> str:
    """
    Keep normal punctuation and line breaks, but remove control characters
    that can make Gmail display mojibake or strange symbols.
    """
    if value is None:
        return ""

    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    allowed_controls = {"\n", "\t"}
    return "".join(
        char for char in text
        if char in allowed_controls or ord(char) >= 32
    ).strip()


def create_gmail_draft(to_email: str, email_data: dict,
                      from_email: str = None) -> Optional[str]:
    """
    Create a REAL Gmail draft using OAuth2 with amin@pinnaclecontentstudio.com
    Requires credentials.json from Google Cloud Console
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        SCOPES = ['https://www.googleapis.com/auth/gmail.compose']

        # Load or create credentials
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    print("⚠️  credentials.json not found!")
                    print("   Please download it from Google Cloud Console:")
                    print("   https://console.cloud.google.com/apis/credentials")
                    print("   1. Create OAuth 2.0 Client ID (Desktop app)")
                    print("   2. Download as JSON")
                    print("   3. Save as 'credentials.json' in this folder")
                    return None

                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for next time
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        # Create Gmail service
        service = build('gmail', 'v1', credentials=creds)

        # Build the email message with UTF-8 encoding.
        # Do not call set_payload() after MIME creation. That can corrupt
        # non-ASCII characters and make Gmail show mojibake/special symbols.
        subject = clean_email_text(email_data.get('subject', ''))
        body = clean_email_text(email_data.get('body', ''))

        signature = """

---
Amin
Founder, Pinnacle Content Studio
amin@pinnaclecontentstudio.com
pinnaclecontent.studio"""

        full_body = body + signature

        message = EmailMessage()
        message['To'] = to_email
        message['Subject'] = subject
        message['From'] = from_email or os.environ.get('GMAIL_SENDER_EMAIL', 'amin@pinnaclecontentstudio.com')
        message.set_content(full_body, subtype='plain', charset='utf-8')

        # Create draft (not send - for review first)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        draft = service.users().drafts().create(
            userId='me',
            body={'message': {'raw': raw}}
        ).execute()

        print(f"  ✓ Gmail draft created: {to_email}")
        return draft['id']

    except Exception as e:
        print(f"  ✗ Error creating Gmail draft: {e}")
        return None


# ============================================================================
# LOGGING
# ============================================================================

def log_to_file(email_data: dict) -> bool:
    """
    Log outreach activity to local JSON file for tracking and analytics.
    """
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "company": email_data['company'],
            "contact_role": email_data['contact_role'],
            "industry": email_data['industry'],
            "subject": email_data['subject'],
            "status": "draft_created",
            "body_preview": email_data['body'][:100] + "...",
        }

        # Append to log file
        log_file = "outreach_log.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        return True

    except Exception as e:
        print(f"  ✗ Error logging: {e}")
        return False


# ============================================================================
# MAIN AGENT LOOP
# ============================================================================

def run_outreach_cycle(num_companies: int = 5, safe_mode: bool = True, dry_run: bool = False, once: bool = False):
    """
    Execute one complete outreach cycle:
    1. Generate company targets
    2. Research each company
    3. Create personalized emails
    4. Create Gmail drafts
    5. Log to tracking file
    """
    print("\n" + "="*70)
    print(f"🚀 PINNACLE OUTREACH CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    # Step 1: Generate targets
    print(f"\n📋 Generating {num_companies} company targets...")
    companies = generate_company_targets(num_companies)
    print(f"✓ Generated {len(companies)} targets")

    real_gmail_drafts_created = 0
    safe_mode_skipped = 0
    dry_run_skipped = 0
    failed_email_generations = 0

    for i, company in enumerate(companies, 1):
        print(f"\n--- Company {i}/{len(companies)}: {company.get('company_name', 'Unknown')} ---")

        # Step 2: Research
        print("  🔍 Researching...")
        company = research_company(company)

        # Step 3: Generate email
        print("  ✍️  Generating email...")
        email_data = generate_outreach_email(company)
        if not email_data:
            print("  ✗ Failed to generate email, skipping")
            failed_email_generations += 1
            continue

        # Step 4: Create Gmail draft
        print("  📧 Preparing Gmail draft action...")
        # Generate a realistic demo email address
        company_name_for_domain = company.get('company_name', 'example')
        company_domain = re.sub(r'[^a-z0-9-]', '', company_name_for_domain.lower().replace(' ', '')) or 'example'
        demo_email = f"contact@{company_domain}.com"
        print(f"  🔎 Planned action: create draft for {demo_email} | SAFE_MODE={safe_mode} | DRY_RUN={dry_run}")

        if safe_mode or dry_run:
            print("  ---------------------------------------------------------")
            print(f"  Email preview | Company: {email_data.get('company', company.get('company_name', 'Unknown'))}")
            print(f"  Planned recipient: {demo_email}")
            print(f"  Subject: {email_data.get('subject', '')}")
            print("  Body:")
            body_lines = str(email_data.get('body', '')).splitlines() or [""]
            for line in body_lines:
                print(f"     {line}")
            print("  ---------------------------------------------------------")

        draft_id = None
        if dry_run:
            print("  ⚠️  DRY_RUN enabled: skipping Gmail draft creation")
            dry_run_skipped += 1
        elif safe_mode:
            print("  ⚠️  SAFE_MODE enabled: skipping Gmail draft creation")
            safe_mode_skipped += 1
        else:
            draft_id = create_gmail_draft(demo_email, email_data)

        # Step 5: Log
        # Note: only real Gmail drafts are logged to the tracking file.
        # Safe-mode/dry-run skipped actions are counted in summary metrics.
        if draft_id:
            print("  📊 Logging to tracking file...")
            log_to_file(email_data)
            real_gmail_drafts_created += 1

        # Small delay between emails
        if i < len(companies):
            time.sleep(2)

    print(f"\n{'='*70}")
    print("✓ CYCLE COMPLETE")
    print(f"  Real Gmail drafts created: {real_gmail_drafts_created}")
    print(f"  Draft actions skipped (SAFE_MODE): {safe_mode_skipped}")
    print(f"  Draft actions skipped (DRY_RUN): {dry_run_skipped}")
    print(f"  Failed email generations: {failed_email_generations}")
    if real_gmail_drafts_created > 0:
        print(f"  Check your Gmail drafts folder: amin@pinnaclecontentstudio.com")
    if once:
        print("  One-cycle run complete. No next cycle scheduled.")
    else:
        print(f"  Next cycle in {CAMPAIGN_INTERVALS['research']} minutes")
    print(f"{'='*70}\n")

    return {
        "real_gmail_drafts_created": real_gmail_drafts_created,
        "safe_mode_skipped": safe_mode_skipped,
        "dry_run_skipped": dry_run_skipped,
        "failed_email_generations": failed_email_generations,
    }


def main():
    """
    Run the agent continuously with scheduled cycles.
    """
    print("""
    ╔═══════════════════════════════════════════════════════════════════╗
    ║  PINNACLE CONTENT STUDIO - AUTONOMOUS OUTREACH AGENT             ║
    ║  Status: ACTIVE                                                   ║
    ║  Mode: Continuous Operation                                       ║
    ║  Output: Controlled by SAFE_MODE / DRY_RUN                        ║
    ║  Email: amin@pinnaclecontentstudio.com                           ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """)

    parser = argparse.ArgumentParser(description="Pinnacle Outreach Agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Draft-action dry run: skips Gmail draft creation only; may still call Anthropic API",
    )
    parser.add_argument("--once", action="store_true", help="Run exactly one outreach cycle and exit")
    parser.add_argument("--safe-mode", choices=["true", "false"], default=None, help="Override SAFE_MODE env var")
    args = parser.parse_args()

    safe_mode = _parse_bool(SAFE_MODE_DEFAULT, default=True)
    dry_run = _parse_bool(DRY_RUN_DEFAULT, default=False)
    if args.safe_mode is not None:
        safe_mode = _parse_bool(args.safe_mode, default=True)
    if args.dry_run:
        dry_run = True

    print(f"Startup config: SAFE_MODE={safe_mode} | DRY_RUN={dry_run}")
    print("Output mode:")
    print("- Gmail draft creation skipped when SAFE_MODE=true or DRY_RUN=true")
    print("- Real Gmail drafts only when SAFE_MODE=false and DRY_RUN=false")
    if dry_run:
        print("Mode note: --dry-run is a draft-action dry run. Gmail draft creation is skipped, but Anthropic API calls may still occur during generation.")
    validate_startup_requirements(safe_mode=safe_mode, dry_run=dry_run)

    cycle_count = 0

    try:
        while True:
            cycle_count += 1
            print(f"\n>>> Cycle #{cycle_count}")

            # Run outreach cycle
            run_outreach_cycle(num_companies=5, safe_mode=safe_mode, dry_run=dry_run, once=args.once)

            if args.once:
                print("\n⏹️  --once enabled: completed one cycle, exiting.")
                break

            # Wait for next cycle
            print(f"⏳ Sleeping for {CAMPAIGN_INTERVALS['research']} minutes...")
            print(f"   (Press Ctrl+C to stop)\n")

            time.sleep(CAMPAIGN_INTERVALS['research'] * 60)

    except KeyboardInterrupt:
        print("\n\n⏹️  Agent stopped by user")
        print(f"Total cycles completed: {cycle_count}")
        print("All drafts logged and saved in Gmail")


if __name__ == "__main__":
    main()
