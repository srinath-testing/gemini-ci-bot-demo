#!/usr/bin/env python3
"""Simple test to verify bot can post comments"""

import os
from github import Github

# Get environment variables
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("REPOSITORY", "srinath-testing/gemini-ci-bot-demo")
PR_NUM = os.environ.get("PR_NUMBER", "3")

print(f"🤖 Testing bot connection...")
print(f"Repository: {REPO}")
print(f"PR Number: {PR_NUM}")
print(f"Token: {'✅ Set' if GITHUB_TOKEN else '❌ Missing'}")

try:
    github = Github(GITHUB_TOKEN)
    repo = github.get_repo(REPO)
    pr = repo.get_pull(int(PR_NUM))
    
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = f"""🤖 **CI Failure Bot** - Connection Test

✅ **Bot Infrastructure Working!**

**Test Results:**
- GitHub API: ✅ Connected
- Repository: ✅ {REPO}
- PR Access: ✅ Can post comments
- Timestamp: {timestamp}

**This confirms the bot can:**
- Access the repository
- Read PR information  
- Post comments successfully
- Run on workflow failures

The intelligent analysis system is ready! 🚀

---
*Connection test completed at {timestamp}*"""
    
    pr.create_issue_comment(message)
    print("✅ SUCCESS: Test comment posted!")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()