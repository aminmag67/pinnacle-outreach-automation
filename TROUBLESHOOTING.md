# TROUBLESHOOTING GUIDE - Pinnacle Outreach Agent

## Setup Issues

### "ANTHROPIC_API_KEY is not set"
**Error message:**
```
RuntimeError: ANTHROPIC_API_KEY is not set. In PowerShell, run: 
$env:ANTHROPIC_API_KEY="your_api_key_here"
```

**Solutions:**
1. Set API key before running:
   ```powershell
   $env:ANTHROPIC_API_KEY="sk-ant-YOUR_KEY"
   python pinnacle_outreach_agent_utf8_fixed.py
   ```

2. Make API key permanent (Windows):
   ```powershell
   [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY","sk-ant-YOUR_KEY","User")
   # Then restart PowerShell
   ```

3. Check if key is set:
   ```powershell
   echo $env:ANTHROPIC_API_KEY
   # Should print: sk-ant-...
   ```

**Prevention:** Save your API key in a secure location (password manager) before running again.

---

### "credentials.json not found"
**Error message:**
```
⚠️  credentials.json not found!
Please download it from Google Cloud Console:
https://console.cloud.google.com/apis/credentials
```

**Solutions:**
1. Download from Google Cloud Console:
   - Go to: https://console.cloud.google.com
   - Select project: "Pinnacle Outreach"
   - Click "Create Credentials" → "OAuth 2.0 Client ID"
   - Type: "Desktop application"
   - Click "Create"
   - Click "Download" (JSON button)
   - Save as `credentials.json` in your pinnacle-outreach folder

2. Verify file location:
   ```
   C:\Users\YOUR_USER\pinnacle-outreach\
   ├── pinnacle_outreach_agent_utf8_fixed.py
   ├── credentials.json  ← Should be here
   ```

3. Check file permissions:
   - Right-click credentials.json
   - Properties → Security → Edit
   - Allow "Read" permission

**Prevention:** Keep credentials.json in version control (don't commit) or back it up safely.

---

## Gmail OAuth Issues

### "Gmail OAuth failed" / "Invalid client"
**Error message:**
```
OAuth flow error: invalid_client or redirect_uri_mismatch
```

**Solutions:**
1. Re-authorize by deleting token.json:
   ```powershell
   cd C:\Users\YOUR_USER\pinnacle-outreach
   rm token.json
   python pinnacle_outreach_agent_utf8_fixed.py
   ```

2. Check OAuth redirect URI in Google Cloud:
   - Go to: https://console.cloud.google.com
   - OAuth 2.0 Client ID settings
   - Authorized redirect URIs should include: `http://localhost:8080/`

3. Verify credentials.json is correct:
   - Open credentials.json
   - Should have "client_id", "client_secret", "auth_uri"

4. Clear browser cache:
   - Close all browser windows
   - Open new incognito window
   - Run agent again

---

### "Gmail drafts not appearing"
**Problem:** Script runs but no drafts show up in Gmail

**Solutions:**
1. Check correct Gmail account:
   - Log in to: https://mail.google.com
   - Verify you're in: amin@pinnaclecontentstudio.com
   - NOT: your personal Gmail account

2. Check Drafts folder:
   - Click left sidebar "Drafts"
   - NOT "Sent" or "Inbox"
   - Refresh page (Ctrl+R)

3. Check for errors in logs:
   - Open `outreach_log.jsonl`
   - Look for "✗ Error" entries
   - Check email address in entry

4. Verify OAuth token is valid:
   ```powershell
   # Delete and re-auth
   rm token.json
   python pinnacle_outreach_agent_utf8_fixed.py
   ```

5. Test manually:
   - Create a test email in Gmail
   - Try to create draft manually
   - If manual works, OAuth scope may be wrong

---

## Text & Encoding Issues

### Garbled text in Gmail (像った・gh？)
**Problem:** Email body shows mojibake or strange Unicode characters

**Solution:** Already fixed in this version!

This version uses:
- ✅ `EmailMessage` (modern Python email)
- ✅ UTF-8 proper encoding
- ✅ `clean_email_text()` function
- ✅ Control character filtering

If you still see garbled text:
1. Verify you're using `pinnacle_outreach_agent_utf8_fixed.py`
2. Check Python version is 3.6+:
   ```powershell
   python --version
   ```
3. Clear old token.json and re-authorize
4. Check Gmail account charset settings

---

### Subject line too long or truncated
**Problem:** Subject line is cut off in Gmail

**Solution:**
Gmail shows ~50 characters max. The code limits subject to 50 chars:
```python
subject = email_data['subject'][:50]
```

To adjust:
1. Edit `generate_outreach_email()` in Python
2. Modify prompt: "Keep subject line to 50 characters max"
3. Change to: "Keep subject line to 60 characters max" (if needed)

**Prevention:** 
- Subject lines are already limited to ~50 chars
- If too long, it will be truncated in Gmail display only

---

## Agent Runtime Issues

### "Agent stops unexpectedly" / Crashes mid-cycle
**Problem:** Script crashes after running 1-2 cycles

**Solutions:**
1. Check error log:
   ```powershell
   type outreach_log.jsonl | tail -20
   # Or open in text editor and look at last entries
   ```

2. Common causes and fixes:
   - **API rate limit**: Wait 1 minute, restart agent
   - **Network error**: Check internet connection
   - **Invalid company**: Agent skips and continues (normal)
   - **Memory issue**: Close other programs, restart

3. Run with error output:
   ```powershell
   python pinnacle_outreach_agent_utf8_fixed.py 2>&1 | tee agent.log
   # Saves full output to agent.log
   ```

4. Check Python version:
   ```powershell
   python --version
   # Must be 3.8 or higher
   ```

---

### "Process hangs" / No output for 10+ minutes
**Problem:** Agent seems frozen, no emails being created

**Solutions:**
1. Check if it's waiting:
   - Script should print "⏳ Sleeping for 30 minutes..." after each cycle
   - If you see this, it's working (just waiting)

2. Force stop and restart:
   ```powershell
   # Ctrl+C to stop
   # Then restart
   python pinnacle_outreach_agent_utf8_fixed.py
   ```

3. Check network:
   ```powershell
   # Ping Anthropic API
   Test-NetConnection api.anthropic.com -Port 443
   # Should say "TcpTestSucceeded : True"
   ```

4. Check API key:
   ```powershell
   echo $env:ANTHROPIC_API_KEY
   # Should show your key, not empty
   ```

---

## Log File Issues

### "Can't read outreach_log.jsonl"
**Problem:** File is locked or corrupted

**Solutions:**
1. Open in text editor:
   - Right-click → Open With → Notepad
   - View raw JSON entries

2. Parse with Python:
   ```python
   import json
   with open('outreach_log.jsonl', 'r') as f:
       for line in f:
           entry = json.loads(line)
           print(f"{entry['timestamp']}: {entry['company']}")
   ```

3. Back up and reset:
   ```powershell
   # Backup current log
   cp outreach_log.jsonl outreach_log_backup.jsonl
   
   # Start fresh
   rm outreach_log.jsonl
   python pinnacle_outreach_agent_utf8_fixed.py
   ```

---

### "Log file keeps growing huge"
**Problem:** outreach_log.jsonl is 100MB+ and slow

**Solutions:**
1. Archive old logs:
   ```powershell
   # Move to archive folder
   mv outreach_log.jsonl archive/outreach_log_2026-05.jsonl
   ```

2. Split by date:
   ```powershell
   # Create monthly logs
   # Edit Python to use: f"outreach_log_{datetime.now().strftime('%Y-%m')}.jsonl"
   ```

3. Clean up:
   ```powershell
   # Keep only recent entries
   tail -10000 outreach_log.jsonl > outreach_log_recent.jsonl
   mv outreach_log_recent.jsonl outreach_log.jsonl
   ```

---

## Performance Issues

### "Agent is too slow" / "API taking forever"
**Problem:** Each cycle takes 5+ minutes, should be 1-2 minutes

**Solutions:**
1. Check internet speed:
   ```powershell
   # Run a speed test
   # Go to speedtest.net or use Ookla speedtest CLI
   ```

2. Reduce API token usage:
   - Lower `max_tokens` in code
   - Generate fewer companies per cycle
   - Use faster model: `claude-sonnet-4-20250514`

3. Optimize settings:
   ```python
   # In Python file:
   max_tokens=400  # Reduce from 600
   num_companies=3  # Reduce from 5
   ```

4. Check system resources:
   - Open Task Manager (Ctrl+Shift+Esc)
   - Check CPU, Memory, Disk usage
   - Close unused programs

---

### "API rate limit exceeded"
**Error message:**
```
anthropic.RateLimitError: rate_limit_exceeded
```

**Solutions:**
1. Wait and retry:
   - Agent automatically waits and retries
   - Check logs for "rate_limit" messages

2. Reduce request frequency:
   ```python
   CAMPAIGN_INTERVALS["research"] = 60  # Increase from 30 min
   ```

3. Reduce daily volume:
   ```python
   CAMPAIGN_INTERVALS["daily_limit"] = 2  # Reduce from 5
   ```

4. Check account limits:
   - Log in to https://console.anthropic.com
   - Check your API usage and rate limits
   - Upgrade plan if needed

---

## Config Issues

### "Invalid setting" / Python syntax error
**Error message:**
```
SyntaxError: invalid syntax on line 42
```

**Solutions:**
1. Check syntax:
   - Python is indent-sensitive (spaces matter)
   - Quotes must be balanced: "hello" not "hello

2. Common mistakes:
   ```python
   # WRONG: Missing quote
   TARGET_LOCATION = "Ventura County, California
   
   # CORRECT:
   TARGET_LOCATION = "Ventura County, California"
   ```

3. Validate changes:
   ```powershell
   # Check syntax without running
   python -m py_compile pinnacle_outreach_agent_utf8_fixed.py
   # If OK, no output. If error, shows line number.
   ```

4. Reset to defaults:
   - Redownload original file
   - Make one change at a time
   - Test each change

---

## Windows Task Scheduler Issues

### "Task runs but no output"
**Problem:** Task Scheduler runs the batch file but no emails appear

**Solutions:**
1. Check task history:
   - Open Task Scheduler
   - Right-click task → History
   - Look for errors

2. Verify batch file exists:
   ```batch
   dir C:\Users\YOUR_USER\pinnacle-outreach\run_pinnacle.bat
   ```

3. Test batch file manually:
   ```powershell
   cd C:\Users\YOUR_USER\pinnacle-outreach
   .\run_pinnacle.bat
   ```

4. Check permissions:
   - Right-click task → Properties
   - Check "Run with highest privileges"
   - Verify user account has access

---

## General Debugging

### "Enable debug mode"
Add to Python for detailed output:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Then add throughout code:
logger.debug(f"Company: {company_name}")
logger.debug(f"Email subject: {email_data['subject']}")
```

### "Test API connection"
```powershell
# Test Anthropic API
$env:ANTHROPIC_API_KEY="sk-ant-YOUR_KEY"

python -c "
import anthropic
client = anthropic.Anthropic()
msg = client.messages.create(model='claude-opus-4-1', max_tokens=10, messages=[{'role': 'user', 'content': 'Hi'}])
print('✓ API connection OK')
"
```

### "Test Gmail OAuth"
```powershell
python -c "
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
print('✓ Gmail libraries installed')
"
```

---

## Contact & Support

**Still stuck?** Check:
1. PINNACLE_README.md - Full guide
2. outreach_log.jsonl - Error details
3. Google Cloud Console - OAuth settings
4. Anthropic Dashboard - API usage

**Common resources:**
- Anthropic Docs: https://docs.anthropic.com
- Google Cloud Docs: https://cloud.google.com/docs
- Python Docs: https://docs.python.org

---

**Last updated:** May 2026  
**Version:** 2.0  
**Status:** Keep this file handy! 🆘
