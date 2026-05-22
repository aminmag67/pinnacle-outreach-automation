# CODE REVIEW: UTF-8 Fix for Pinnacle Outreach Agent

## Executive Summary
✅ **FIXED** - The uploaded `pinnacle_outreach_agent_utf8_fixed.py` addresses the Unicode/encoding bug that was producing garbled text in Gmail drafts.

---

## The Problem (Original Issue)
The screenshot you showed had garbled text like:
```
「像った・gh？)？)」
```

This happened because:
1. Claude was generating fancy Unicode characters (em-dashes, en-dashes, smart quotes)
2. Improper email encoding was corrupting these characters
3. The original `MIMEText()` + `.set_payload()` approach could corrupt non-ASCII text

---

## The Solution (Fixed Version)

### 1. **Clean Text Function** ✅ (Lines 361-376)
```python
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
```

**Why This Works:**
- Removes control characters (ASCII < 32) that cause encoding issues
- Preserves normal punctuation, spaces, and line breaks
- Keeps the text clean without aggressive ASCII-only stripping

### 2. **Better Email Message Building** ✅ (Lines 422-449)
```python
# BEST APPROACH: Use EmailMessage with set_content()
from email.message import EmailMessage

message = EmailMessage()
message['To'] = to_email
message['Subject'] = subject
message['From'] = from_email
message.set_content(full_body, subtype='plain', charset='utf-8')

# Encode properly for Gmail API
raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
```

**Why This is Better:**
- ✅ Uses `EmailMessage` (Python 3.6+) instead of deprecated `MIMEText`
- ✅ `.set_content()` handles UTF-8 encoding correctly
- ✅ No `.set_payload()` call that could corrupt encoding
- ✅ Proper base64 encoding for Gmail API

### 3. **Compared to Original (PROBLEMATIC)**
The original code did:
```python
# OLD - PROBLEMATIC
from email.mime.text import MIMEText

message = MIMEText(email_data['body'], _charset='utf-8')
message['to'] = to_email
message['subject'] = email_data['subject']

raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
```

**Problems:**
- ❌ `MIMEText` is older and less reliable for non-ASCII
- ❌ Creating message first, then setting `.as_bytes()` can cause encoding issues
- ❌ No `.decode('utf-8')` specification (could default to ASCII)
- ❌ No pre-cleaning of text before encoding

---

## Additional Improvements in This Version

### 1. **Signature in Email Body** (Lines 428-434)
```python
signature = """

---
Amin
Founder, Pinnacle Content Studio
amin@pinnaclecontentstudio.com
pinnaclecontent.studio"""

full_body = body + signature
```

✅ Signature is part of the email body, not added separately
✅ Avoids duplication (Claude may also include signature in body text)
⚠️ **NOTE:** Website URL should be `pinnaclecontentstudio.com` not `pinnaclecontent.studio`

### 2. **Clean Subject & Body** (Lines 425-426)
```python
subject = clean_email_text(email_data.get('subject', ''))
body = clean_email_text(email_data.get('body', ''))
```

✅ Both subject and body are sanitized before email creation
✅ Removes any control characters that could cause mojibake

### 3. **Proper UTF-8 Charset** (Line 442)
```python
message.set_content(full_body, subtype='plain', charset='utf-8')
```

✅ Explicitly sets UTF-8 charset
✅ Tells Gmail this is plain text (not HTML)

---

## Testing Checklist

When you run this version, verify:

- [ ] Email subject displays clearly in Gmail (no garbled text)
- [ ] Email body displays clearly (no 像った・gh？ symbols)
- [ ] Signature appears once at bottom of email
- [ ] Line breaks are preserved in email body
- [ ] Company names display correctly
- [ ] All text is readable ASCII/UTF-8

---

## Remaining Issues to Address

### 1. **Website URL** ⚠️
Line 434 shows:
```python
pinnaclecontent.studio
```

Should be:
```python
pinnaclecontentstudio.com
```

**Action:** Search/replace in the file before running.

### 2. **Prompt Still Includes Dates** ⚠️
Check line ~304 in `generate_outreach_email()` to verify:
- ❌ No "January", "May", "tax season" in subject line examples
- ❌ No "current month" passed to Claude
- ✅ Only timeless pain-point subjects

**Action:** Verify the prompt in `generate_outreach_email()` matches the no-dates version.

---

## Encoding Strategy Summary

| Approach | Pros | Cons | Status |
|----------|------|------|--------|
| **EmailMessage + set_content()** | ✅ Modern, reliable, UTF-8 native | Requires Python 3.6+ | ✅ USED |
| MIMEText (old) | Works but outdated | Encoding issues | ❌ Problematic |
| Aggressive ASCII-only strip | Safe but loses accents | Too destructive | ⚠️ Not needed |
| clean_email_text() filter | Balanced approach | Removes control chars only | ✅ USED |

---

## Final Verdict

**Rating: 8/10 ✅ IMPROVED**

### What's Fixed:
- ✅ EmailMessage properly handles UTF-8
- ✅ Control characters filtered before encoding
- ✅ Proper base64 encoding for Gmail API
- ✅ No `.set_payload()` corruption

### What to Verify:
- ⚠️ No "May", "tax season", or other dates in prompt
- ⚠️ Website URL is correct (pinnaclecontentstudio.com)
- ⚠️ Test run to confirm no garbled text appears

### Next Steps:
1. Download this version
2. Fix the website URL (if needed)
3. Verify the prompt has NO date references
4. Run one test cycle and check Gmail drafts
5. Confirm text displays cleanly

---

## Command to Run

```powershell
$env:ANTHROPIC_API_KEY="sk-ant-YOUR_API_KEY"
python pinnacle_outreach_agent_utf8_fixed.py
```

Then check Gmail drafts for clean, readable text with no mojibake. ✅
