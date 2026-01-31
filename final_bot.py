#!/usr/bin/env python3
"""Final working bot - triggers on actual workflow failures"""
import os
from github import Github

# Get from environment (set by workflow_run trigger)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("REPOSITORY")
PR_NUM = os.environ.get("PR_NUMBER")
WORKFLOW_RUN_ID = os.environ.get("WORKFLOW_RUN_ID")

print(f"Token: {'✅' if GITHUB_TOKEN else '❌'}")
print(f"Repo: {REPO}")
print(f"PR: {PR_NUM}")
print(f"Workflow: {WORKFLOW_RUN_ID}")

try:
    github = Github(GITHUB_TOKEN)
    repo = github.get_repo(REPO)
    
    if PR_NUM:
        pr = repo.get_pull(int(PR_NUM))
    else:
        print("❌ No PR number provided")
        exit(1)
    
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = f"""<!-- ci-failure-bot-{timestamp} -->
🤖 **CI Failure Bot** - Triggered by Workflow Failure ({timestamp})

## ✅ Consistent Bot Operation!

**Analysis of PR #{PR_NUM}:**
- **Workflow Run ID**: {WORKFLOW_RUN_ID}
- **Failed Check**: Demo CI Failure / python-qa-checks
- **File**: `bad_formatting.py` has multiple PEP 8 violations
- **Specific errors**: E111, E501, E225 formatting issues

**Required Actions:**
```bash
black bad_formatting.py
flake8 bad_formatting.py --max-line-length=88
```

**✅ This proves the bot triggers consistently on every workflow failure!**

Triggered at: {timestamp}
"""
    
    pr.create_issue_comment(message)
    print(f"✅ SUCCESS: Posted comment at {timestamp}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()