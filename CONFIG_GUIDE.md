# CONFIGURATION GUIDE - Pinnacle Outreach Agent

## Overview
This guide details all configurable settings in the Pinnacle Outreach Agent. Edit the Python file to customize behavior.

---

## TARGET LOCATION SETTINGS

### Geographic Targeting
```python
TARGET_LOCATION = "Ventura County and Los Angeles County, California"
TARGET_COMPANY_SIZE = "micro to small (1-100 employees)"
```

**Change to target different areas:**
- Southern California: "San Diego County and Orange County, California"
- Bay Area: "San Francisco Bay Area, California"
- Texas: "Houston Metropolitan Area, Texas"
- National: "United States"

---

## INDUSTRY TARGETING

### Industries List
```python
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
```

**Add more industries:**
```python
INDUSTRIES.append("your new industry here")
```

**Remove industries:**
```python
INDUSTRIES.remove("fitness and wellness centers")
```

---

## TARGET ROLES

### Contact Roles to Target
```python
TARGET_ROLES = [
    # Ownership/Executive
    "Owner", "CEO", "Founder", "Business Owner",
    
    # Operations
    "Manager", "General Manager", "Operations Manager",
    "Business Manager", "Executive Director", "Principal",
    
    # Marketing
    "Head of Marketing", "Marketing Manager", "Marketing Director",
    "Content Manager", "Communications Manager",
    "VP of Marketing", "Director of Marketing",
    
    # HR
    "HR Manager", "HR Director", "Human Resources Manager",
    "Training Manager", "Learning & Development Manager",
    "VP of Human Resources",
    
    # Sales
    "Business Development Manager", "Sales Manager", "Sales Director",
    
    # Industry-Specific
    "Practice Manager", "Clinic Manager", "Office Manager",
    "Service Manager", "Project Manager", "Client Success Manager",
    "Account Manager",
    
    # C-Suite
    "Chief Operating Officer", "COO",
    "Chief Marketing Officer", "CMO",
]
```

**Customize for your target:**
- Reduce to just "Owner" and "CEO" for very small businesses
- Add role titles from your industry research
- Remove roles that don't apply

---

## CAMPAIGN INTERVALS & LIMITS

### Timing Configuration
```python
CAMPAIGN_INTERVALS = {
    "research": 30,      # minutes between cycles
    "daily_limit": 5,    # max emails per day
    "cooldown": 60       # minutes between emails to same company
}
```

### Adjust for Your Needs

**Light outreach (conservative):**
```python
"research": 60,         # Every hour
"daily_limit": 10,      # 10 emails/day max
```

**Aggressive outreach (fast):**
```python
"research": 15,         # Every 15 minutes
"daily_limit": 20,      # 20 emails/day max
```

**Daily cadence (business hours only):**
```python
"research": 120,        # Every 2 hours
"daily_limit": 5,       # 5 emails/day
```

---

## EMAIL CONFIGURATION

### Sender Email
Default:
```python
from_email="amin@pinnaclecontentstudio.com"
```

Change if using different email account:
```python
from_email="your.email@yourdomain.com"
```

### Website/Landing Page
In email signature and CTAs:
```python
website = "pinnaclecontentstudio.com"
```

Change to your domain:
```python
website = "yourdomain.com"
```

### Email Content Adjustments
Edit the `generate_outreach_email()` function prompt to customize:

**Subject line style** (modify prompt lines):
- Remove: "DO NOT say 'free branding report'"
- Add: "Subject should mention [your specific pain point]"

**Body copy** (modify prompt lines):
- "Pinnacle Content Studio helps..." → describe YOUR service
- "free resources/tools" → describe WHAT resources

**CTA (Call To Action)** (modify prompt lines):
```
- MAIN CTA: Visit {website} to see how you can help
- Secondary CTA: Schedule a call if interested
```

---

## API MODEL SELECTION

### Current Model
```python
model="claude-opus-4-1"
```

### Change to Different Claude Models
```python
# For faster/cheaper responses (less sophisticated)
model="claude-sonnet-4-20250514"

# For maximum quality (slower/more expensive)
model="claude-opus-4-6"

# For balanced approach (recommended)
model="claude-opus-4-1"
```

### Token Limits
```python
max_tokens=1500        # Company generation
max_tokens=500         # Company research
max_tokens=600         # Email generation
```

Increase for longer responses, decrease for shorter/faster responses.

---

## LOGGING CONFIGURATION

### Log File
```python
log_file = "outreach_log.jsonl"
```

Change filename:
```python
log_file = "my_outreach_log.jsonl"
```

### Log Location
Logs are saved in the same folder as the script. To use a different folder:
```python
import os
log_folder = "/path/to/logs"
log_file = os.path.join(log_folder, "outreach_log.jsonl")
```

### Log Format
Each line is a JSON object:
```json
{
  "timestamp": "2026-05-22T14:30:00.123456",
  "company": "Company Name",
  "contact_role": "Title",
  "industry": "Industry",
  "location": "City, CA",
  "subject": "Email subject",
  "status": "draft_created",
  "body_preview": "First 100 words of email..."
}
```

---

## GMAIL OAUTH CONFIGURATION

### Scopes (Permissions)
```python
SCOPES = ['https://www.googleapis.com/auth/gmail.compose']
```

Current scope allows:
- ✅ Create drafts
- ✅ Send emails (if modified)
- ❌ Read existing emails

To expand permissions, add scopes:
```python
SCOPES = [
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.readonly'  # Add read access
]
```

### Credentials Files
- **credentials.json**: OAuth config (download from Google Cloud)
- **token.json**: Auto-created on first run (stores auth token)

To re-authorize: Delete `token.json` and restart agent.

---

## COMPANY GENERATION SETTINGS

### Number of Companies Per Cycle
In `run_outreach_cycle()`:
```python
num_companies=5
```

Change to generate more/fewer per cycle:
```python
num_companies=10         # Generate 10 per cycle
num_companies=3          # Generate 3 per cycle
```

### Avoid/Focus Lists in Prompt
Edit `generate_company_targets()` prompt to change targets:

Current AVOID:
```
- Salesforce, HubSpot, Deloitte, Accenture
- Companies with 500+ employees
- Fortune 1000
```

Current FOCUS ON:
```
- Solo practitioners and small agencies (1-10 people)
- Service-based companies
- Companies with 1-100 employees
```

Customize to your perfect target.

---

## ADVANCED: CUSTOM FILTERING

### Skip Certain Industries
Add to company generation logic:
```python
def generate_company_targets():
    # ... existing code ...
    # Filter out companies you don't want
    filtered_companies = [c for c in companies 
                         if c["industry"] not in ["fitness", "real estate"]]
    return filtered_companies
```

### Skip Certain Company Sizes
```python
def generate_company_targets():
    # ... existing code ...
    # Only target companies with 1-50 employees
    filtered = [c for c in companies if c["size"] in ["startup", "small"]]
    return filtered
```

### Weighted Random Selection
```python
import random
contact_role = random.choices(
    TARGET_ROLES,
    weights=[1, 1, 2, 1, 1, ...],  # Weight higher-priority roles
    k=1
)[0]
```

---

## ENVIRONMENT VARIABLES

### API Key Setup
```powershell
# Session-only (recommended for testing)
$env:ANTHROPIC_API_KEY="sk-ant-YOUR_KEY"

# Permanent (Windows)
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY","sk-ant-YOUR_KEY","User")

# Permanent (Mac/Linux)
export ANTHROPIC_API_KEY="sk-ant-YOUR_KEY"
# Add to ~/.zshrc or ~/.bashrc for persistence
```

### Custom Variables
Add to Python:
```python
MY_DOMAIN = os.environ.get("MY_DOMAIN", "example.com")
MY_EMAIL = os.environ.get("MY_EMAIL", "contact@example.com")
```

Set in PowerShell:
```powershell
$env:MY_DOMAIN="yourdomain.com"
$env:MY_EMAIL="your.email@yourdomain.com"
```

---

## PERFORMANCE TUNING

### For Slow Internet
- Increase `research` interval: 60 minutes (instead of 30)
- Decrease `max_tokens`: 400 (instead of 600)
- Reduce `num_companies`: 3 (instead of 5)

### For Limited API Credits
- Increase `research` interval: 120 minutes
- Reduce `daily_limit`: 2 emails/day
- Use cheaper model: `claude-sonnet-4-20250514`

### For Maximum Speed
- Decrease `research` interval: 15 minutes
- Use parallel processing (advanced Python)
- Increase `num_companies`: 10 per cycle

---

## TESTING CONFIGURATION

### Single-Run Test
Modify `main()` to run once:
```python
def main():
    run_outreach_cycle(num_companies=1)  # Just 1 email
    # Don't loop, just exit
```

### Dry-Run (No Gmail)
Modify `create_gmail_draft()`:
```python
def create_gmail_draft(...):
    # Just print, don't create
    print(f"Would create: {email_data['subject']}")
    return "dry-run-id"
```

### Debug Mode
Add verbose logging:
```python
print(f"[DEBUG] Generating for: {company_name}")
print(f"[DEBUG] Industry: {industry}")
print(f"[DEBUG] Contact role: {contact_role}")
```

---

## RESET TO DEFAULTS

Keep original values for reference:
```python
# Default settings
DEFAULT_TARGET_LOCATION = "Ventura County and Los Angeles County, California"
DEFAULT_COMPANY_SIZE = "micro to small (1-100 employees)"
DEFAULT_INDUSTRIES = [...]  # Full list

# Current settings (modify as needed)
TARGET_LOCATION = os.environ.get("TARGET_LOCATION", DEFAULT_TARGET_LOCATION)
COMPANY_SIZE = os.environ.get("COMPANY_SIZE", DEFAULT_COMPANY_SIZE)
```

---

## SUMMARY

Most common changes:
1. **Location**: `TARGET_LOCATION`
2. **Industries**: `INDUSTRIES = [...]`
3. **Email domain**: `website = "yourdomain.com"`
4. **Timing**: `CAMPAIGN_INTERVALS["research"] = 60`
5. **Company count**: `num_companies=10`

Make one change, test, then adjust!
