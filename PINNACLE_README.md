# PINNACLE OUTREACH AGENT - SETUP & DEPLOYMENT GUIDE

**Version:** 2.0 (UTF-8 Fixed)  
**Status:** Production Ready  
**Last Updated:** May 22, 2026

---

## 📋 TABLE OF CONTENTS
1. [Quick Start](#quick-start)
2. [System Overview](#system-overview)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the Agent](#running-the-agent)
6. [Troubleshooting](#troubleshooting)
7. [File Manifest](#file-manifest)

---

## QUICK START

### Prerequisites
- Python 3.8+ installed on Windows/Mac/Linux
- Anthropic API key (sk-ant-...)
- Google Cloud OAuth credentials (credentials.json)

### 60-Second Setup
```powershell
# 1. Navigate to folder
cd C:\Users\YOUR_USER\pinnacle-outreach

# 2. Install dependencies
pip install anthropic google-auth-oauthlib google-auth-httplib2 google-api-python-client gspread python-dotenv

# 3. Set API key
$env:ANTHROPIC_API_KEY="sk-ant-YOUR_API_KEY"

# 4. Run agent
python pinnacle_outreach_agent_utf8_fixed.py
```

OAuth browser will open automatically on first run. ✅

---

## SYSTEM OVERVIEW

### What It Does
1. **Generates** 5 local small businesses per cycle (Ventura/LA Counties)
2. **Researches** each company for personalization
3. **Creates** personalized cold emails with Claude AI
4. **Drafts** emails in Gmail for manual review
5. **Logs** all activity to `outreach_log.jsonl`
6. **Repeats** every 30 minutes continuously

### Key Features
- ✅ **UTF-8 Encoding Fixed** - No more garbled text in Gmail
- ✅ **Gmail OAuth2** - Real Gmail drafts with manual review
- ✅ **AI-Powered** - Claude generates personalized subject lines & bodies
- ✅ **No Dates** - Subject lines focus on pain points, not timing
- ✅ **Local Targeting** - Small businesses 1-100 employees
- ✅ **Trackable** - JSON logs for analytics

### Architecture
```
User runs agent
        ↓
Generate 5 company targets (Claude)
        ↓
Research each company (Claude)
        ↓
Generate personalized email (Claude)
        ↓
Create Gmail draft (OAuth2)
        ↓
Log to outreach_log.jsonl
        ↓
Wait 30 minutes, repeat
```

---

## INSTALLATION

### Step 1: Install Python Packages
```bash
pip install anthropic google-auth-oauthlib google-auth-httplib2 google-api-python-client gspread python-dotenv
```

**Packages:**
- `anthropic` - Claude API client
- `google-auth-oauthlib` - Google OAuth2 flow
- `google-auth-httplib2` - HTTP transport
- `google-api-python-client` - Gmail API
- `gspread` - (optional, for future expansions)
- `python-dotenv` - Environment variable management

### Step 2: Get API Key
1. Log in to Anthropic console: https://console.anthropic.com
2. Create/copy your API key (starts with `sk-ant-`)
3. Keep it safe - you'll use it to run the agent

### Step 3: Set Up Google OAuth
1. Go to: https://console.cloud.google.com
2. Create new project: "Pinnacle Outreach"
3. Enable **Gmail API**
4. Create **OAuth 2.0 Client ID** (type: Desktop app)
5. Download as JSON → save as **credentials.json** in your pinnacle-outreach folder

### Step 4: Folder Structure
```
C:\Users\YOUR_USER\pinnacle-outreach\
├── pinnacle_outreach_agent_utf8_fixed.py
├── credentials.json (auto-generated from Step 3)
├── token.json (auto-created on first run)
└── outreach_log.jsonl (auto-created on first run)
```

---

## CONFIGURATION

### API Key Setup (Windows PowerShell)
```powershell
# Option 1: Session only (closes when PowerShell closes)
$env:ANTHROPIC_API_KEY="sk-ant-YOUR_API_KEY_HERE"

# Option 2: Permanent (set once, persists across sessions)
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY","sk-ant-YOUR_API_KEY_HERE","User")
```

### Target Location & Industries
Edit these in the Python file:
```python
TARGET_LOCATION = "Ventura County and Los Angeles County, California"
TARGET_COMPANY_SIZE = "micro to small (1-100 employees)"

INDUSTRIES = [
    "local marketing agencies",
    "regional training companies",
    "local tech startups",
    # ... 17 more industries
]
```

### Email Configuration
- **From:** amin@pinnaclecontentstudio.com
- **CTA Website:** pinnaclecontentstudio.com
- **CTA:** "Visit our website for free resources" + "Schedule a 15-min call"

### Cycle Settings
```python
CAMPAIGN_INTERVALS = {
    "research": 30,      # minutes between cycles
    "daily_limit": 5,    # max emails per day
    "cooldown": 60       # minutes between emails to same company
}
```

---

## RUNNING THE AGENT

### Option 1: Manual (for testing)
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-YOUR_KEY"
python pinnacle_outreach_agent_utf8_fixed.py
```
- Generates 5 emails
- Creates Gmail drafts
- Waits 30 minutes
- Repeats until you press Ctrl+C

### Option 2: Background Process (Recommended)
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-YOUR_KEY"
Start-Process python -ArgumentList "pinnacle_outreach_agent_utf8_fixed.py" -NoNewWindow
```
- Closes PowerShell immediately
- Agent continues running in background ✅
- Check Gmail drafts folder for emails

### Option 3: Windows Task Scheduler (Most Professional)

**Create batch file** (`run_pinnacle.bat`):
```batch
@echo off
cd C:\Users\YOUR_USER\pinnacle-outreach
set ANTHROPIC_API_KEY=sk-ant-YOUR_API_KEY_HERE
python pinnacle_outreach_agent_utf8_fixed.py
```

**Schedule it:**
1. Press `Win + R` → type `taskschd.msc` → Enter
2. Right-click "Task Scheduler Library" → **New Task**
3. **Name:** "Pinnacle Outreach Agent"
4. **Trigger:** "At startup" or "Repeat every 30 minutes"
5. **Action:** Browse to `run_pinnacle.bat`
6. Check "Run with highest privileges"
7. Click OK

Now it runs automatically! ✅

---

## MONITORING

### Check Gmail Drafts
1. Go to Gmail: https://mail.google.com
2. Account: amin@pinnaclecontentstudio.com
3. Look for **Drafts** folder
4. Review emails before sending (or delete if not interested)

### View Logs
Check `outreach_log.jsonl` for activity:
```json
{
  "timestamp": "2026-05-22T14:30:00.123456",
  "company": "Westlake Marketing Group",
  "contact_role": "Owner",
  "industry": "local marketing agencies",
  "location": "Westlake Village, CA",
  "subject": "Help dominate Westlake's competitive market",
  "status": "draft_created",
  "body_preview": "Hi Owner, We help local marketing agencies..."
}
```

---

## TROUBLESHOOTING

### "ANTHROPIC_API_KEY is not set"
**Fix:** Set environment variable before running:
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-YOUR_KEY"
```

### "credentials.json not found"
**Fix:** Download from Google Cloud Console (see Installation Step 3)

### "Gmail OAuth failed"
**Fix:** Delete `token.json` and restart - will re-authorize in browser

### Garbled text in emails (像った・gh？)
**Fix:** Already fixed in UTF-8 version! This version uses proper EmailMessage encoding.

### Agent stops unexpectedly
**Fix:** Check outreach_log.jsonl for errors. Common issues:
- API rate limit (wait 1 minute)
- Network issue (check internet)
- Invalid company target (skipped automatically)

### Gmail drafts not appearing
**Fix:** 
1. Check Gmail account is amin@pinnaclecontentstudio.com
2. Check Drafts folder (not sent, not inbox)
3. Try refreshing Gmail

---

## FILE MANIFEST

This package contains:

| File | Purpose | Language |
|------|---------|----------|
| `pinnacle_outreach_agent_utf8_fixed.py` | Main agent - generate, research, email, log | Python 3.8+ |
| `PINNACLE_README.md` | This file - setup & deployment guide | Markdown |
| `QUICK_REFERENCE.txt` | Command cheat sheet | Plain text |
| `CONFIG_GUIDE.md` | Detailed configuration options | Markdown |
| `TROUBLESHOOTING.md` | Common issues & solutions | Markdown |
| `EMAIL_EXAMPLES.txt` | Sample generated emails | Plain text |

---

## KEY STATS

- **Daily Emails:** 5 per cycle × ~48 cycles/day = 240/day (configurable)
- **Cycle Time:** 30 minutes
- **Target Size:** 1-100 employees
- **Target Location:** Ventura & LA Counties, CA
- **Email Type:** Cold outreach → Gmail draft
- **Model:** Claude Opus 4.1
- **Encoding:** UTF-8 (no mojibake)

---

## NEXT STEPS

1. ✅ Download all files from package
2. ✅ Install Python packages
3. ✅ Get Anthropic API key
4. ✅ Set up Google OAuth credentials
5. ✅ Test run: `python pinnacle_outreach_agent_utf8_fixed.py`
6. ✅ Check Gmail drafts folder
7. ✅ Set up Task Scheduler for 24/7 operation

---

## SUPPORT

**Issues?** Check:
- `TROUBLESHOOTING.md` - Common problems
- `outreach_log.jsonl` - Error details
- Gmail drafts folder - Email output
- Command output - Real-time feedback

**Questions?** Review:
- `CONFIG_GUIDE.md` - Configuration
- `EMAIL_EXAMPLES.txt` - Sample output
- `QUICK_REFERENCE.txt` - Commands

---

**Status:** ✅ Production Ready  
**Tested:** May 2026  
**Encoding:** UTF-8 Fixed (No mojibake)  
**Ready to deploy!** 🚀
