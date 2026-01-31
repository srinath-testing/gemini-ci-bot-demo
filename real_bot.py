#!/usr/bin/env python3
"""REAL CI Failure Bot - analyzes actual build logs"""
import os
import io
import zipfile
import requests
from github import Github

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("REPOSITORY")
PR_NUM = os.environ.get("PR_NUMBER")
WORKFLOW_RUN_ID = os.environ.get("WORKFLOW_RUN_ID")

try:
    github = Github(GITHUB_TOKEN)
    repo = github.get_repo(REPO)
    pr = repo.get_pull(int(PR_NUM))
    
    # Get ACTUAL build logs from failed jobs
    workflow_run = repo.get_workflow_run(int(WORKFLOW_RUN_ID))
    jobs = workflow_run.jobs()
    
    real_errors = []
    for job in jobs:
        if job.conclusion == "failure":
            # Get actual logs
            logs_url = job.logs_url
            if logs_url:
                headers = {
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github.v3+json",
                }
                response = requests.get(logs_url, headers=headers, timeout=30)
                if response.status_code == 200:
                    raw = response.content
                    if raw[:2] == b"PK":  # ZIP file
                        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                            parts = []
                            for name in zf.namelist():
                                if name.endswith(".txt"):
                                    parts.append(zf.read(name).decode("utf-8", "replace"))
                            log_text = "\n".join(parts)
                    else:
                        log_text = raw.decode("utf-8", "replace")
                    
                    # Extract REAL errors from logs
                    if "FAILED" in log_text and "test_" in log_text:
                        real_errors.append(f"**{job.name}**: Unit test failures detected in logs")
                    elif "flake8" in log_text and "error" in log_text.lower():
                        real_errors.append(f"**{job.name}**: Flake8 style violations detected")
                    elif "black" in log_text and "would reformat" in log_text:
                        real_errors.append(f"**{job.name}**: Black formatting issues detected")
                    else:
                        real_errors.append(f"**{job.name}**: Build failure (check logs)")
    
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if real_errors:
        message = f"""<!-- ci-failure-bot-{timestamp} -->
🤖 **CI Failure Bot** - Real Error Analysis ({timestamp})

## ❌ Actual Build Failures Detected

**Analysis of PR #{PR_NUM}:**
- **Workflow Run ID**: {WORKFLOW_RUN_ID}
- **Real Issues Found**: {len(real_errors)}

**Actual Errors from Build Logs:**
{chr(10).join(f"- {error}" for error in real_errors)}

**Required Actions:**
Based on the actual failures above, please:
1. Check the specific error messages in the CI logs
2. Fix the identified issues
3. Test locally before pushing

**✅ This analysis is based on REAL build log content, not assumptions.**

Analyzed at: {timestamp}
"""
    else:
        message = f"""<!-- ci-failure-bot-{timestamp} -->
🤖 **CI Failure Bot** - Analysis ({timestamp})

## ⚠️ Build Failed - Unable to Parse Logs

**Analysis of PR #{PR_NUM}:**
- **Workflow Run ID**: {WORKFLOW_RUN_ID}
- **Status**: Could not extract specific error details from logs

**Required Actions:**
Please check the CI logs manually for specific error messages.

Analyzed at: {timestamp}
"""
    
    pr.create_issue_comment(message)
    print(f"✅ SUCCESS: Posted REAL analysis based on actual logs")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()