#!/usr/bin/env python3
"""INTELLIGENT CI Failure Bot - analyzes PRIMARY failure cause"""
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
    
    # PRIORITY-BASED ERROR DETECTION
    import_errors = []
    test_errors = []
    qa_errors = []
    other_errors = []
    
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
                    
                    # PRIORITIZE ERROR TYPES (most critical first)
                    if "ModuleNotFoundError" in log_text or "ImportError" in log_text:
                        import_errors.append(f"**{job.name}**: Import/dependency errors")
                    elif "FAILED" in log_text and "test_" in log_text and "AssertionError" in log_text:
                        test_errors.append(f"**{job.name}**: Unit test assertion failures")
                    elif "flake8" in log_text or "black" in log_text or "isort" in log_text:
                        qa_errors.append(f"**{job.name}**: Code quality issues")
                    else:
                        other_errors.append(f"**{job.name}**: Build failure")
    
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # ANALYZE PRIMARY FAILURE (highest priority first)
    if import_errors:
        # IMPORT ERRORS are highest priority
        message = f"""<!-- ci-failure-bot-{timestamp} -->
🤖 **CI Failure Bot** - Import Error Analysis ({timestamp})

## ❌ Import/Dependency Errors Detected

**Analysis of PR #{PR_NUM}:**
- **Workflow Run ID**: {WORKFLOW_RUN_ID}
- **Primary Issue**: Missing dependencies or incorrect imports
- **Failed Jobs**: {len(import_errors)}

**Critical Errors Found:**
{chr(10).join(f"- {error}" for error in import_errors)}

**Technical Diagnosis:**
- ModuleNotFoundError or ImportError in build logs
- Missing required packages or misspelled package names
- Import statements referencing non-existent modules

**Required Actions:**
```bash
# Check import statements for typos
python -c "import your_module_name"

# Install missing dependencies
pip install package_name

# Verify all imports work
python -m py_compile your_file.py
```

**Root Cause**: Missing or incorrectly named dependencies.

**Priority**: HIGH - Import errors prevent code execution.

Analyzed at: {timestamp}
"""
    elif test_errors:
        # TEST ERRORS are second priority
        message = f"""<!-- ci-failure-bot-{timestamp} -->
🤖 **CI Failure Bot** - Test Failure Analysis ({timestamp})

## ❌ Unit Test Failures Detected

**Analysis of PR #{PR_NUM}:**
- **Workflow Run ID**: {WORKFLOW_RUN_ID}
- **Primary Issue**: Test assertion failures
- **Failed Jobs**: {len(test_errors)}

**Test Failures Found:**
{chr(10).join(f"- {error}" for error in test_errors)}

**Required Actions:**
```bash
python -m pytest -v
# Fix failing test assertions
```

**Root Cause**: Test assertion mismatches.

Analyzed at: {timestamp}
"""
    elif qa_errors:
        # QA ERRORS are lowest priority
        message = f"""<!-- ci-failure-bot-{timestamp} -->
🤖 **CI Failure Bot** - Code Quality Analysis ({timestamp})

## ❌ Code Quality Issues Detected

**Analysis of PR #{PR_NUM}:**
- **Workflow Run ID**: {WORKFLOW_RUN_ID}
- **Primary Issue**: Code formatting violations
- **Failed Jobs**: {len(qa_errors)}

**Quality Issues Found:**
{chr(10).join(f"- {error}" for error in qa_errors)}

**Required Actions:**
```bash
black .
isort .
flake8 . --max-line-length=88
```

**Root Cause**: Code doesn't follow style guidelines.

Analyzed at: {timestamp}
"""
    else:
        # FALLBACK for other errors
        all_errors = other_errors
        message = f"""<!-- ci-failure-bot-{timestamp} -->
🤖 **CI Failure Bot** - Build Failure Analysis ({timestamp})

## ❌ Build Failures Detected

**Analysis of PR #{PR_NUM}:**
- **Workflow Run ID**: {WORKFLOW_RUN_ID}
- **Issues Found**: {len(all_errors)}

**Errors Found:**
{chr(10).join(f"- {error}" for error in all_errors)}

**Required Actions:**
Check the CI logs for specific error details.

Analyzed at: {timestamp}
"""
    
    pr.create_issue_comment(message)
    print(f"✅ SUCCESS: Posted INTELLIGENT analysis based on PRIMARY failure type")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()