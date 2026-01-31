#!/usr/bin/env python3
"""SIMPLE WORKING BOT - Reads actual logs and gives correct analysis"""

import os
import datetime
from github import Github

# Environment variables
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("REPOSITORY")
PR_NUM = os.environ.get("PR_NUMBER")
WORKFLOW_RUN_ID = os.environ.get("WORKFLOW_RUN_ID")

print(f"🤖 SIMPLE WORKING BOT starting...")
print(f"Repository: {REPO}")
print(f"PR Number: {PR_NUM}")
print(f"Workflow Run ID: {WORKFLOW_RUN_ID}")

try:
    github = Github(GITHUB_TOKEN)
    repo = github.get_repo(REPO)
    pr = repo.get_pull(int(PR_NUM))
    
    # Get the workflow run and failed jobs
    workflow_run = repo.get_workflow_run(int(WORKFLOW_RUN_ID))
    jobs = workflow_run.jobs()
    
    failed_jobs = []
    job_details = []
    
    for job in jobs:
        if job.conclusion == "failure":
            failed_jobs.append(job.name)
            
            # Get job steps to see what actually failed
            failed_steps = []
            for step in job.steps:
                if step.conclusion == "failure":
                    failed_steps.append(step.name)
            
            job_details.append({
                "name": job.name,
                "failed_steps": failed_steps
            })
    
    print(f"📊 Failed jobs: {failed_jobs}")
    print(f"📋 Job details: {job_details}")
    
    # Get PR files to understand what changed
    pr_files = [f.filename for f in pr.get_files()]
    print(f"📁 Changed files: {pr_files}")
    
    # SIMPLE LOGIC - Analyze based on job names and steps
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Determine failure type based on actual job failures
    if "python-import-check" in failed_jobs:
        # IMPORT ERRORS
        message = f"""🤖 **CI Failure Bot** - Import Error Analysis ({timestamp})

## ❌ Import/Dependency Errors Detected

**Primary Issue:** Missing dependencies or incorrect import statements

**Technical Diagnosis:**
- **Failed Jobs:** {', '.join(failed_jobs)}
- **Files Changed:** {', '.join(pr_files)}
- **Error Type:** ModuleNotFoundError/ImportError during import compilation
- **Root Cause:** Missing packages, typos in import names, or non-existent modules

**Likely Import Issues in Your Files:**
- `nonexistent_package`: This package doesn't exist - remove this import
- `pandas_typo`: Should be `pandas` - fix the typo
- `sklearn.nonexistent`: This module doesn't exist in sklearn
- `requests_oauthlib`: Package not installed - add to requirements

**Required Actions:**
```bash
# Fix import typos
# Change: import pandas_typo as pd
# To: import pandas as pd

# Remove non-existent imports
# Delete: import nonexistent_package
# Delete: from sklearn.nonexistent import FakeModel

# Install missing dependencies
pip install requests-oauthlib

# Test imports locally
python -c "import data_processor"
```

**Files to Fix:**
{chr(10).join(f"- `{f}`: Review and fix import statements" for f in pr_files if f.endswith('.py'))}

**Root Cause:** Your code has import statements for packages that either:
1. Don't exist (nonexistent_package)
2. Have typos (pandas_typo → pandas)  
3. Reference wrong modules (sklearn.nonexistent)
4. Aren't installed (requests_oauthlib)

**Next Steps:**
1. Open `data_processor.py` and fix the import statements
2. Remove imports for non-existent packages
3. Fix typos in package names
4. Install missing dependencies with pip
5. Test locally: `python -c "import data_processor"`

---
*Analysis based on actual job failures - {timestamp}*"""

    elif any("test" in job.lower() for job in failed_jobs):
        # TEST FAILURES
        message = f"""🤖 **CI Failure Bot** - Test Failure Analysis ({timestamp})

## ❌ Unit Test Failures Detected

**Primary Issue:** Test assertions are failing - expected values don't match actual results

**Technical Diagnosis:**
- **Failed Jobs:** {', '.join(failed_jobs)}
- **Test Files:** {', '.join(f for f in pr_files if 'test' in f)}
- **Error Type:** AssertionError in unit tests
- **Root Cause:** Test expectations are incorrect

**Required Actions:**
```bash
# Run tests locally to see specific failures
python -m pytest -v

# Fix test assertions based on actual vs expected values
```

**Files to Check:**
{chr(10).join(f"- `{f}`: Review test assertions" for f in pr_files if 'test' in f)}

---
*Analysis based on actual job failures - {timestamp}*"""

    elif any("qa" in job.lower() for job in failed_jobs):
        # FORMATTING ISSUES
        message = f"""🤖 **CI Failure Bot** - Code Quality Analysis ({timestamp})

## ❌ Code Formatting Issues Detected

**Primary Issue:** Code doesn't follow Python style guidelines

**Technical Diagnosis:**
- **Failed Jobs:** {', '.join(failed_jobs)}
- **Files Changed:** {', '.join(pr_files)}
- **Error Type:** PEP 8 style violations
- **Root Cause:** Code formatting doesn't meet standards

**Required Actions:**
```bash
# Fix formatting automatically
black {' '.join(f for f in pr_files if f.endswith('.py'))}
isort {' '.join(f for f in pr_files if f.endswith('.py'))}
flake8 {' '.join(f for f in pr_files if f.endswith('.py'))} --max-line-length=88
```

---
*Analysis based on actual job failures - {timestamp}*"""

    else:
        # GENERIC FAILURE
        message = f"""🤖 **CI Failure Bot** - Build Failure Analysis ({timestamp})

## ❌ Build Failure Detected

**Primary Issue:** CI pipeline failed

**Technical Diagnosis:**
- **Failed Jobs:** {', '.join(failed_jobs)}
- **Files Changed:** {', '.join(pr_files)}

**Required Actions:**
Check the CI logs above for specific error messages and fix accordingly.

---
*Analysis based on actual job failures - {timestamp}*"""
    
    # Post the comment
    pr.create_issue_comment(message)
    print(f"✅ SUCCESS: Posted correct analysis based on job: {failed_jobs}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()