# PINNACLE OUTREACH AGENT - SETUP & DEPLOYMENT GUIDE

**Version:** 2.1 (Safety Migration)  
**Status:** Safety Setup In Progress  
**Last Updated:** May 22, 2026

---

## 📋 TABLE OF CONTENTS
1. [Quick Start](#quick-start)
2. [System Overview](#system-overview)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the Agent Safely](#running-the-agent-safely)
6. [Troubleshooting](#troubleshooting)
7. [File Manifest](#file-manifest)

---

## QUICK START

### Prerequisites
- Python 3.8+ installed on Windows/Mac/Linux
- Anthropic API key (for generation steps)
- Google Cloud OAuth credentials (`credentials.json`) **only when you explicitly enable Gmail draft creation**

### 60-Second Safe Setup
```powershell
# 1. Navigate to folder
cd C:\Users\YOUR_USER\pinnacle-outreach

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create local env file from template
Copy-Item .env.example .env

# 4. Edit .env (keep SAFE_MODE=true while testing)
# ANTHROPIC_API_KEY=your_real_key_here
# SAFE_MODE=true
# DRY_RUN=false

# 5. Run in safe default mode
python pinnacle_outreach_agent_utf8_fixed.py