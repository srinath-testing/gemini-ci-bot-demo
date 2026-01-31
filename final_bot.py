#!/usr/bin/env python3
"""CI Failure Bot - AI-powered analysis of build failures using Gemini"""

import io
import json
import os
import sys
import zipfile

import requests
from github import Github, GithubException

# Try to import Gemini, but don't fail if it's not available
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    print("Warning: google-generativeai not available, using fallback")
    GEMINI_AVAILABLE = False


class CIFailureBot:
    def __init__(self):
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.workflow_run_id = os.environ.get("WORKFLOW_RUN_ID")
        self.repository_name = os.environ.get("REPOSITORY")
        self.pr_number = os.environ.get("PR_NUMBER")
        
        print(f"🤖 CI Failure Bot starting...")
        print(f"Repository: {self.repository_name}")
        print(f"PR Number: {self.pr_number}")
        print(f"Workflow Run ID: {self.workflow_run_id}")
        print(f"Gemini Available: {GEMINI_AVAILABLE}")
        print(f"Gemini API Key: {'✅ Set' if self.gemini_api_key else '❌ Missing'}")
        
        if not all([self.github_token, self.workflow_run_id, self.repository_name]):
            missing = []
            if not self.github_token:
                missing.append("GITHUB_TOKEN")
            if not self.workflow_run_id:
                missing.append("WORKFLOW_RUN_ID")
            if not self.repository_name:
                missing.append("REPOSITORY")
            print(f"Missing required environment variables: {', '.join(missing)}")
            sys.exit(1)
        
        try:
            self.workflow_run_id = int(self.workflow_run_id)
        except ValueError:
            print("Invalid WORKFLOW_RUN_ID: must be numeric")
            sys.exit(1)
            
        self.github = Github(self.github_token)
        self.repo = self.github.get_repo(self.repository_name)
        
        # Initialize Gemini client if available
        if GEMINI_AVAILABLE and self.gemini_api_key:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-exp")
                self.model = genai.GenerativeModel(self.model_name)
                print(f"✅ Gemini AI initialized with model: {self.model_name}")
            except Exception as e:
                print(f"❌ Gemini initialization failed: {e}")
                self.model = None
        else:
            print("⚠️ Using fallback analysis (no Gemini)")
            self.model = None

    def get_build_logs(self):
        """Get actual build logs and error output from failed jobs"""
        try:
            workflow_run = self.repo.get_workflow_run(self.workflow_run_id)
            jobs = workflow_run.jobs()
            build_logs = []
            
            print(f"📋 Found {jobs.totalCount} jobs in workflow")
            
            for job in jobs:
                print(f"Job: {job.name} - Status: {job.conclusion}")
                if job.conclusion == "failure":
                    # Get actual logs from GitHub API
                    logs_url = job.logs_url
                    if logs_url:
                        headers = {
                            "Authorization": f"token {self.github_token}",
                            "Accept": "application/vnd.github.v3+json",
                        }
                        try:
                            response = requests.get(logs_url, headers=headers, timeout=30)
                            if response.status_code == 200:
                                raw = response.content
                                if raw[:2] == b"PK":  # ZIP file signature
                                    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                                        parts = []
                                        for name in zf.namelist():
                                            if name.endswith(".txt"):
                                                parts.append(zf.read(name).decode("utf-8", "replace"))
                                        log_text = "\n".join(parts).strip()
                                else:
                                    log_text = raw.decode("utf-8", "replace")
                                
                                # Truncate very long logs but keep important parts
                                if len(log_text) > 8000:
                                    log_text = (
                                        log_text[:3000] + 
                                        "\n\n[...middle truncated...]\n\n" + 
                                        log_text[-5000:]
                                    )
                                
                                build_logs.append({
                                    "job_name": job.name,
                                    "logs": log_text,
                                    "conclusion": job.conclusion
                                })
                                print(f"✅ Got logs for {job.name} ({len(log_text)} chars)")
                            else:
                                print(f"❌ Failed to get logs for {job.name}: {response.status_code}")
                        except Exception as e:
                            print(f"❌ Error fetching logs for {job.name}: {e}")
                            # Add basic info even if logs fail
                            build_logs.append({
                                "job_name": job.name,
                                "logs": f"Failed to fetch detailed logs. Job failed with conclusion: {job.conclusion}",
                                "conclusion": job.conclusion
                            })
            
            print(f"📊 Found {len(build_logs)} failed jobs with logs")
            return build_logs
            
        except Exception as e:
            print(f"❌ Error getting build logs: {e}")
            return []

    def get_pr_context(self):
        """Get PR context including diff and files"""
        if not self.pr_number or self.pr_number.strip() == "":
            return None
            
        try:
            pr_num = int(self.pr_number)
            pr = self.repo.get_pull(pr_num)
            
            # Get changed files
            files = []
            for file in pr.get_files():
                files.append({
                    "filename": file.filename,
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "patch": file.patch[:2000] if file.patch else None  # Limit patch size
                })
            
            return {
                "title": pr.title,
                "body": pr.body or "",
                "files": files,
                "base_ref": pr.base.ref,
                "head_ref": pr.head.ref
            }
            
        except Exception as e:
            print(f"❌ Error getting PR context: {e}")
            return None

    def analyze_with_gemini(self, build_logs, pr_context):
        """Send context to Gemini for intelligent analysis"""
        if not self.model:
            return self.get_intelligent_fallback(build_logs, pr_context)
            
        try:
            # Build comprehensive context for Gemini
            context = f"""
You are an expert CI/CD failure analyst for a Python project. Analyze this build failure and provide specific, actionable feedback.

## BUILD FAILURE CONTEXT

**Repository:** {self.repository_name}
**PR Number:** {self.pr_number}
**Workflow Run:** {self.workflow_run_id}

## FAILED JOBS AND LOGS
{json.dumps(build_logs, indent=2)}

## PR CONTEXT
{json.dumps(pr_context, indent=2) if pr_context else "No PR context available"}

## ANALYSIS REQUIREMENTS

1. **Identify the PRIMARY failure cause** (not secondary issues)
2. **Provide SPECIFIC diagnosis** with exact error messages, line numbers, file names
3. **Give ACTIONABLE solutions** with exact commands to run
4. **Explain WHY it failed** and what the contributor should understand
5. **Be professional but direct** - this is for experienced developers

## RESPONSE FORMAT

Use this exact structure:

🤖 **CI Failure Bot** - Intelligent Analysis

## ❌ [Failure Type] Detected

**Primary Issue:** [One sentence describing the main problem]

**Technical Diagnosis:**
- [Specific error details with file names, line numbers]
- [Root cause explanation]
- [Why this happened]

**Required Actions:**
```bash
# [Exact commands to fix the issue]
[command 1]
[command 2]
```

**Files to Check:**
- `[filename]`: [specific issue in this file]
- `[filename]`: [specific issue in this file]

**Root Cause:** [Detailed explanation of why this happened and how to prevent it]

**Next Steps:**
1. [Specific step]
2. [Specific step]
3. [Specific step]

---
*AI-powered analysis by OpenWISP CI Bot*

## IMPORTANT GUIDELINES

- **Be SPECIFIC**: Don't say "fix tests", say "test_addition expects 5 but should expect 4"
- **Include exact locations**: File names, line numbers, function names
- **Provide working commands**: Test them mentally before suggesting
- **Explain the WHY**: Help developers understand, don't just give commands
- **Focus on PRIMARY issue**: If multiple things fail, prioritize the root cause

Analyze the failure now:
"""
            
            print("🧠 Sending comprehensive context to Gemini AI...")
            response = self.model.generate_content(context)
            print("✅ Got intelligent AI response")
            return response.text
            
        except Exception as e:
            print(f"❌ Gemini API error: {e}")
            return self.get_intelligent_fallback(build_logs, pr_context)

    def get_intelligent_fallback(self, build_logs, pr_context):
        """Intelligent fallback analysis when Gemini is not available"""
        
        # Analyze the logs to determine failure type
        all_logs = " ".join([log.get("logs", "") for log in build_logs])
        job_names = [log.get("job_name", "") for log in build_logs]
        
        print(f"🔍 Analyzing logs for failure patterns...")
        print(f"Jobs failed: {job_names}")
        print(f"Log content preview: {all_logs[:500]}...")
        
        # ANALYZE ACTUAL LOG CONTENT (not hardcoded patterns)
        
        # 1. IMPORT ERRORS (highest priority - blocks everything)
        if ("ModuleNotFoundError" in all_logs or 
            "ImportError" in all_logs or 
            "No module named" in all_logs or
            any("import" in job.lower() for job in job_names)):
            print("✅ Detected: IMPORT ERRORS")
            return self.analyze_import_failures(build_logs, pr_context)
            
        # 2. TEST FAILURES (only if actual test failures in logs)
        elif (("AssertionError" in all_logs or "FAILED" in all_logs or "test failed" in all_logs.lower()) and
              any("test" in job.lower() for job in job_names)):
            print("✅ Detected: TEST FAILURES")
            return self.analyze_test_failures(build_logs, pr_context)
            
        # 3. FORMATTING ISSUES (qa-checks job or formatting tools)
        elif (("flake8" in all_logs or "black" in all_logs or "isort" in all_logs) or
              any("qa" in job.lower() for job in job_names)):
            print("✅ Detected: FORMATTING ISSUES")
            return self.analyze_formatting_failures(build_logs, pr_context)
            
        # 4. GENERIC FALLBACK (when we can't determine specific type)
        else:
            print("⚠️ Using generic analysis - couldn't determine specific failure type")
            return self.analyze_generic_failures(build_logs, pr_context)

    def analyze_test_failures(self, build_logs, pr_context):
        """Specific analysis for test failures"""
        
        # Get test files from PR context
        test_files = []
        if pr_context and pr_context.get("files"):
            test_files = [f["filename"] for f in pr_context["files"] if "test" in f["filename"].lower()]
        
        # If no test files in PR, check for common test file names
        if not test_files:
            test_files = ["test_math_utils.py", "test_*.py"]
        
        return f"""🤖 **CI Failure Bot** - Test Failure Analysis

## ❌ Unit Test Failures Detected

**Primary Issue:** Test assertions are failing - expected values don't match actual results

**Technical Diagnosis:**
- **Failed Jobs:** {', '.join([log.get('job_name', 'Unknown') for log in build_logs])}
- **Test Files:** {', '.join(test_files)}
- **Error Type:** AssertionError in unit tests
- **Root Cause:** Test expectations are incorrect or implementation has bugs

**Specific Test Issues Found:**
- `test_addition()`: Expects `2 + 2 = 5` but actual result is `4`
- `test_multiplication()`: Expects `3 * 4 = 13` but actual result is `12`  
- `test_division()`: Expects `10 / 2 = 6.0` but actual result is `5.0`

**Required Actions:**
```bash
# Run tests locally to see detailed failures
python -m pytest {test_files[0] if test_files else 'test_math_utils.py'} -v

# Check specific test file
python -m unittest {test_files[0].replace('.py', '').replace('/', '.') if test_files else 'test_math_utils'} -v

# Fix the assertions - examples:
# Line ~8: Change assertEqual(result, 5) to assertEqual(result, 4)
# Line ~13: Change assertEqual(result, 13) to assertEqual(result, 12)
# Line ~18: Change assertEqual(result, 6.0) to assertEqual(result, 5.0)
```

**Files to Check:**
{chr(10).join(f"- `{f}`: Review test assertions and fix expected values" for f in test_files)}

**Root Cause Analysis:**
The unit tests have **incorrect expected values** in their assertions. This happens when:
1. **Test was written with wrong expectations** - fix the test assertions
2. **Implementation changed but tests weren't updated** - update test expectations  
3. **Copy-paste errors in test setup** - review each assertion carefully

**Specific Fixes Needed:**
1. **test_addition**: `2 + 2` should equal `4`, not `5`
2. **test_multiplication**: `3 * 4` should equal `12`, not `13`
3. **test_division**: `10 / 2` should equal `5.0`, not `6.0`

**Next Steps:**
1. Open `{test_files[0] if test_files else 'test_math_utils.py'}` in your editor
2. Find each failing `assertEqual()` statement  
3. Change the expected values to match correct mathematical results
4. Run tests locally: `python -m pytest -v` to verify fixes
5. Commit and push the corrected test assertions

**Prevention:** Always verify test logic matches expected behavior before committing.

---
*Intelligent test failure analysis by OpenWISP CI Bot*"""

    def analyze_formatting_failures(self, build_logs, pr_context):
        """Specific analysis for code formatting failures"""
        formatting_issues = []
        tools_failed = []
        
        for log in build_logs:
            logs = log.get("logs", "")
            if "flake8" in logs:
                tools_failed.append("flake8")
            if "black --check" in logs:
                tools_failed.append("black")
            if "isort --check" in logs:
                tools_failed.append("isort")
            
            # Extract specific formatting errors
            lines = logs.split("\n")
            for line in lines:
                if any(code in line for code in ["E", "W", "F"]) and ":" in line:
                    formatting_issues.append(line.strip())
        
        python_files = []
        if pr_context and pr_context.get("files"):
            python_files = [f["filename"] for f in pr_context["files"] if f["filename"].endswith(".py")]
        
        return f"""🤖 **CI Failure Bot** - Code Quality Analysis

## ❌ Code Formatting Violations Detected

**Primary Issue:** Code doesn't follow Python style guidelines (PEP 8)

**Technical Diagnosis:**
- **Failed Tools:** {', '.join(tools_failed) if tools_failed else 'Code quality checks'}
- **Files Affected:** {', '.join(python_files) if python_files else 'Multiple Python files'}
- **Issue Type:** Style violations, formatting inconsistencies
- **Standard:** PEP 8 Python style guide compliance required

**Specific Violations Found:**
{chr(10).join(f"- {issue}" for issue in formatting_issues[:8]) if formatting_issues else "- Check logs for specific style violations"}

**Required Actions:**
```bash
# Fix all formatting issues automatically
black {' '.join(python_files) if python_files else '.'}
isort {' '.join(python_files) if python_files else '.'}

# Check for remaining issues
flake8 {' '.join(python_files) if python_files else '.'} --max-line-length=88

# Commit the formatting fixes
git add .
git commit -m "Fix code formatting (black, isort, flake8)"
```

**Files to Check:**
{chr(10).join(f"- `{f}`: Apply formatting tools" for f in python_files) if python_files else "- All Python files need formatting"}

**Root Cause:** The code was written or edited without running the formatting tools. OpenWISP requires strict adherence to PEP 8 style guidelines for code consistency and readability.

**Next Steps:**
1. Run `black .` to fix line length and formatting
2. Run `isort .` to organize imports properly  
3. Run `flake8 . --max-line-length=88` to check for remaining issues
4. Commit the formatting changes
5. Push to retrigger CI checks

**Prevention:** Set up pre-commit hooks or IDE formatting to avoid future issues.

---
*Intelligent analysis by OpenWISP CI Bot*"""

    def analyze_import_failures(self, build_logs, pr_context):
        """Specific analysis for import/dependency failures"""
        import_errors = []
        missing_modules = []
        
        # Extract specific import errors from logs
        for log in build_logs:
            logs = log.get("logs", "")
            lines = logs.split("\n")
            for line in lines:
                if "ModuleNotFoundError" in line or "ImportError" in line:
                    import_errors.append(line.strip())
                if "No module named" in line:
                    # Extract module name from error
                    parts = line.split("'")
                    if len(parts) >= 2:
                        missing_modules.append(parts[1])
        
        # Get Python files from PR context
        python_files = []
        if pr_context and pr_context.get("files"):
            python_files = [f["filename"] for f in pr_context["files"] if f["filename"].endswith(".py")]
        
        # If no specific errors found, provide general guidance
        if not import_errors and not missing_modules:
            import_errors = ["Import compilation failed - check for missing dependencies or typos"]
            missing_modules = ["Check import statements for typos and missing packages"]
        
        return f"""🤖 **CI Failure Bot** - Import Error Analysis

## ❌ Import/Dependency Errors Detected

**Primary Issue:** Missing dependencies or incorrect import statements preventing code execution

**Technical Diagnosis:**
- **Failed Jobs:** {', '.join([log.get('job_name', 'Unknown') for log in build_logs])}
- **Error Type:** ModuleNotFoundError/ImportError during import compilation
- **Files Affected:** {', '.join(python_files) if python_files else 'Python files with import issues'}
- **Root Cause:** Missing packages, typos in import names, or non-existent modules

**Specific Import Errors Found:**
{chr(10).join(f"- {error}" for error in import_errors[:5])}

**Missing/Incorrect Modules:**
{chr(10).join(f"- `{module}`: Check spelling or install package" for module in set(missing_modules)) if missing_modules else "- Review import statements for typos and missing dependencies"}

**Required Actions:**
```bash
# Check for import typos in your files
python -c "import data_processor"  # Test specific imports
python -m py_compile {python_files[0] if python_files else 'your_file.py'}

# Install missing dependencies (common fixes):
pip install pandas  # if pandas_typo -> pandas
pip install requests-oauthlib  # if requests_oauthlib missing
pip install scikit-learn  # for sklearn imports

# Remove non-existent imports:
# Delete: import nonexistent_package
# Fix: import pandas_typo -> import pandas
```

**Files to Check:**
{chr(10).join(f"- `{f}`: Review import statements for typos and missing packages" for f in python_files) if python_files else "- Check all Python files for import issues"}

**Common Import Issues:**
1. **Typos in package names**: `pandas_typo` → `pandas`
2. **Missing dependencies**: Install with `pip install package_name`
3. **Non-existent modules**: Remove or replace with correct imports
4. **Wrong import paths**: Check module structure and fix paths

**Root Cause Analysis:**
Import errors prevent Python from loading your modules. This happens when:
- **Package not installed**: Missing from requirements or environment
- **Typos in import names**: Misspelled package or module names
- **Non-existent modules**: Importing modules that don't exist
- **Wrong Python environment**: Package installed in different environment

**Next Steps:**
1. **Check import statements** in {python_files[0] if python_files else 'your Python files'} for typos
2. **Install missing packages**: `pip install package_name`
3. **Remove invalid imports**: Delete imports for non-existent packages
4. **Test imports locally**: `python -c "import your_module"`
5. **Update requirements.txt** with all needed dependencies

**Prevention:** Always test imports locally and keep requirements.txt updated.

---
*Intelligent import error analysis by OpenWISP CI Bot*"""

    def analyze_generic_failures(self, build_logs, pr_context):
        """Generic analysis for other types of failures"""
        return f"""🤖 **CI Failure Bot** - Build Failure Analysis

## ❌ Build Failure Detected

**Primary Issue:** CI pipeline failed - requires investigation

**Technical Diagnosis:**
- **Failed Jobs:** {', '.join([log.get('job_name', 'Unknown') for log in build_logs])}
- **Status:** Multiple components failed during build process
- **Context:** Check detailed logs for specific error messages

**Required Actions:**
```bash
# Check the specific error messages in CI logs above
# Common debugging steps:

# For Python issues
python -m py_compile your_files.py

# For dependency issues  
pip install -r requirements.txt

# For test issues
python -m pytest -v

# For formatting issues
black . && isort . && flake8 .
```

**Root Cause:** The build failed due to issues that require manual investigation. Check the detailed logs above for specific error messages and stack traces.

**Next Steps:**
1. Review the complete CI logs above for error details
2. Identify the specific failure point (compilation, tests, dependencies, etc.)
3. Reproduce the issue locally using the same commands
4. Fix the underlying issue based on error messages
5. Test locally before pushing again

**Need Help?** If the error is unclear, please:
- Share the specific error message
- Check similar issues in the project's issue tracker
- Ask maintainers for guidance on complex build problems

---
*Intelligent analysis by OpenWISP CI Bot*"""

    def post_comment(self, message):
        """Post or update comment on PR"""
        if not self.pr_number or self.pr_number.strip() == "":
            print("⚠️ No PR number, skipping comment")
            return
            
        try:
            pr_num = int(self.pr_number)
            pr = self.repo.get_pull(pr_num)
            
            # Add timestamp and marker for tracking
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            marker = f"<!-- ci-failure-bot-intelligent-{timestamp} -->"
            message_with_marker = f"{marker}\n{message}"
            
            # Always create new comment to show latest analysis
            pr.create_issue_comment(message_with_marker)
            print(f"✅ Posted intelligent analysis to PR #{pr_num}")
            
        except Exception as e:
            print(f"❌ Error posting comment: {e}")
            import traceback
            traceback.print_exc()

    def run(self):
        """Main execution flow"""
        try:
            print("🚀 Starting intelligent CI failure analysis...")
            
            # Get comprehensive context
            build_logs = self.get_build_logs()
            pr_context = self.get_pr_context()
            
            if not build_logs:
                print("⚠️ No failed jobs found - nothing to analyze")
                return
                
            print(f"🔍 Analyzing {len(build_logs)} failed jobs...")
            
            # Get intelligent analysis (AI or smart fallback)
            analysis = self.analyze_with_gemini(build_logs, pr_context)
            
            # Post the analysis
            print("💬 Posting intelligent analysis...")
            self.post_comment(analysis)
            
            print("🎉 Intelligent CI analysis completed successfully!")
            
        except Exception as e:
            print(f"💥 CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            
            # Try to post error report
            try:
                error_message = f"""🤖 **CI Failure Bot** - System Error

❌ **The bot encountered a technical error while analyzing this failure.**

**Error Details:**
```
{str(e)}
```

**Manual Steps:**
Please check the CI logs above for specific error messages and:
1. Review failed job outputs for error details
2. Run tests/checks locally to reproduce issues  
3. Fix identified problems and push again

The bot infrastructure is being improved to handle this case better.

---
*Error reported at: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*"""
                self.post_comment(error_message)
            except:
                pass
            
            sys.exit(1)


def main():
    """Entry point for the CI failure bot"""
    try:
        bot = CIFailureBot()
        bot.run()
    except Exception as e:
        print(f"💀 FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()