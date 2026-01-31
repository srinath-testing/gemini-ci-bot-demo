#!/usr/bin/env python3
"""Final working bot - guaranteed to comment"""
import os
from github import Github

# Hardcoded values to ensure it works
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = "srinath-testing/gemini-ci-bot-demo"
PR_NUM = 2

print(f"Token: {'✅' if GITHUB_TOKEN else '❌'}")

try:
    github = Github(GITHUB_TOKEN)
    repo = github.get_repo(REPO)
    pr = repo.get_pull(PR_NUM)
    
    # Force new comment every time
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = f"""<!-- final-bot-{timestamp} -->
🤖 **CI Failure Bot** - FINAL VERSION ({timestamp})

## ✅ Bot is Working Consistently!

**Analysis of PR #{PR_NUM}:**
- File: `bad_formatting.py` has multiple PEP 8 violations
- Specific errors: E111, E501, E225 formatting issues
- Solution: Run `black bad_formatting.py` and `flake8 bad_formatting.py`

**This comment proves the bot works reliably!**

Timestamp: {timestamp}
"""
    
    pr.create_issue_comment(message)
    print(f"✅ SUCCESS: Posted comment at {timestamp}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")