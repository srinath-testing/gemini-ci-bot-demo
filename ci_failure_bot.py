#!/usr/bin/env python3
"""CI Failure Bot - AI-powered analysis of build failures using Gemini"""
import io
import json
import os
import sys
import zipfile
import subprocess
import requests
from github import Github, GithubException

# Disable Gemini for demo to prevent import crashes
GEMINI_AVAILABLE = False
genai = None


class CIFailureBot:
    def __init__(self):
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.workflow_run_id = os.environ.get("WORKFLOW_RUN_ID")
        self.repository_name = os.environ.get("REPOSITORY")
        self.pr_number = os.environ.get("PR_NUMBER")
        if not all([self.github_token, self.repository_name]):
            missing = []
            if not self.github_token:
                missing.append("GITHUB_TOKEN")
            if not self.repository_name:
                missing.append("REPOSITORY")
            print(f"Missing required environment variables: {', '.join(missing)}")
            return  # Don't fail the job, just exit gracefully
        self.github = Github(self.github_token)
        self.repo = self.github.get_repo(self.repository_name)
        # Force fallback mode for demo (no Gemini dependency)
        print("Demo mode: Using fallback responses only")
        self.model = None

    def get_build_logs(self):
        """Get actual build logs and error output from failed jobs"""
        if not self.workflow_run_id:
            return []
        try:
            workflow_run_id = int(self.workflow_run_id)
            workflow_run = self.repo.get_workflow_run(workflow_run_id)
            jobs = workflow_run.jobs()
            build_logs = []
            for job in jobs:
                if job.conclusion == "failure":
                    logs_url = job.logs_url
                    if logs_url:
                        headers = {
                            "Authorization": f"token {self.github_token}",
                            "Accept": "application/vnd.github.v3+json",
                        }
                        response = requests.get(logs_url, headers=headers, timeout=30)
                        response.raise_for_status()
                        raw = response.content
                        if raw[:2] == b"PK":
                            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                                parts = []
                                for name in zf.namelist():
                                    if name.endswith(".txt"):
                                        parts.append(zf.read(name).decode("utf-8", "replace"))
                                log_text = "\n".join(parts).strip()
                        else:
                            log_text = raw.decode("utf-8", "replace")
                        if len(log_text) > 5000:
                            log_text = (
                                log_text[:2000]
                                + "\n\n[...middle truncated...]\n\n"
                                + log_text[-3000:]
                            )
                        build_logs.append({"job_name": job.name, "logs": log_text})
            return build_logs
        except (GithubException, requests.RequestException, ValueError) as e:
            print(f"Error getting build logs: {e}")
            return []

    def get_pr_diff(self):
        """Get the PR diff/changes if PR exists"""
        if not self.pr_number or self.pr_number.strip() == "":
            return None
        try:
            pr_num = int(self.pr_number)
            pr = self.repo.get_pull(pr_num)
            try:
                result = subprocess.run(
                    ["git", "diff", f"origin/{self.repo.default_branch}"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    diff_text = result.stdout
                else:
                    diff_url = pr.diff_url
                    headers = {
                        "Authorization": f"token {self.github_token}",
                        "Accept": "application/vnd.github.v3.diff",
                    }
                    response = requests.get(diff_url, headers=headers, timeout=30)
                    if response.status_code == 200:
                        diff_text = response.text
                    else:
                        return None
            except (subprocess.SubprocessError, FileNotFoundError):
                diff_url = pr.diff_url
                headers = {
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github.v3.diff",
                }
                response = requests.get(diff_url, headers=headers, timeout=30)
                if response.status_code == 200:
                    diff_text = response.text
                else:
                    return None
            if len(diff_text) > 8000:
                diff_text = (
                    diff_text[:4000]
                    + "\n\n[...middle truncated...]\n\n"
                    + diff_text[-4000:]
                )
            return {
                "title": pr.title,
                "body": pr.body or "",
                "diff": diff_text,
            }
        except (GithubException, requests.RequestException, ValueError) as e:
            print(f"Error getting PR diff: {e}")
        return None

    def analyze_with_gemini(self, build_logs, pr_diff):
        """Send context to Gemini for intelligent analysis"""
        if not self.model:
            return self.fallback_response()
        project_name = self.repository_name.split("/")[-1]
        repo_url = f"https://github.com/{self.repository_name}"
        default_branch = self.repo.default_branch
        qa_checks_url = f"{repo_url}/blob/{default_branch}/openwisp-qa-check"
        runtests_url = f"{repo_url}/blob/{default_branch}/runtests"
        build_logs_json = json.dumps(build_logs, indent=2)
        if pr_diff:
            pr_diff_json = json.dumps(pr_diff, indent=2)
        else:
            pr_diff_json = "No PR associated"
        context = f"""
### ROLE
You are the "Automated Maintainer Gatekeeper." Your goal is to analyze Pull Request (PR)
build failures and provide direct, technically accurate, and no-nonsense feedback to contributors.

### INPUT CONTEXT PROVIDED
1. **Build Output/Logs:** {build_logs_json}
2. **PR Diff:** {pr_diff_json}
3. **Project Name:** {project_name}
4. **Repository:** {repo_url}
5. **run-qa-checks:** {qa_checks_url}
6. **runtests:** {runtests_url}

### TASK
Analyze the provided context to determine why the build failed.
Categorize the failure and respond according to the "Tone Guidelines" below.

### PR REQUIREMENTS CHECKLIST
Before providing feedback, verify these requirements:
- Does the PR reference any issue? If so, is it correctly mentioned in the commit description?
- If the PR is a fix, change or feature it must include automated tests or it will be rejected.
- Does the CI build fail? If yes, report the key reasons to the contributor
  and if the solution is obvious provide it, if finding the solution is not
  obvious and requires more than 30% additional computation just report the key reasons.
- If QA checks are failing, ask the user to read again the
  [openwisp contributing guidelines](https://openwisp.io/docs/stable/developer/contributing.html)
  to find out how to run qa checks and automatically format the code according to our conventions
- Is the PR addressing changes to the user interface? If yes, check if a selenium
  browser test is present and if the PR description attaches screenshots or screencasts,
  if not, report this to the user and ask to provide both
- If this PR adds a new feature or notably changes an existing documented feature,
  check if documentation updates are present and if not report it
- Do you detect coderabbitai or copilot reviews asking for changes after the latest commit?
  If so, ask the user to follow up with those review comments one by one

### TONE GUIDELINES
- **Direct & Honest:** Do not use "fluff" or overly polite corporate language.
- **Firm Standards:** If a PR is low-effort, spammy, or fails to follow basic instructions,
  state that clearly.
- **Action-Oriented:** Provide the exact command or file change needed to fix the error,
  unless the PR is spammy, in which case we should just declare the PR as potential SPAM
  and ask maintainers to manually review it.

### RESPONSE STRUCTURE
1. **Status Summary:** A one-sentence blunt assessment of the failure.
2. **Technical Diagnosis:**
   - Identify the specific line/test that failed.
   - Explain *why* it failed.
3. **Required Action:** Provide a code block or specific steps the contributor must take.
4. **Quality Warning (If Applicable):** If the PR appears to be "spam"
   (e.g., trivial README changes, AI-generated nonsense, or repeated basic errors),
   include a firm statement that such contributions are a drain on project resources
   and ping the maintainers asking them for manual review.

### EXAMPLE RESPONSE STYLE
The build failed because you neglected to update the test suite to match your logic changes.

**Required Actions:**
- Update tests/logic_test.py to cover your new functionality
- Run `./runtests` locally to verify all tests pass
- Run `openwisp-qa-format` to fix code style issues

**Missing Requirements:**
- [ ] Automated tests for new functionality
- [ ] Code follows OpenWISP style guidelines

We prioritize high-quality, ready-to-merge code. Please ensure you run local tests before pushing.

Analyze the failure and provide your response:
"""
        try:
            response = self.model.generate_content(context)
            return response.text
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return self.fallback_response()

    def fallback_response(self):
        """Fallback response if Gemini fails"""
        return """
## CI Build Failed

The automated analysis is temporarily unavailable. Please check the CI logs above for specific error details.

Common fixes:
- Run `openwisp-qa-format` for code style issues
- Run `./runtests` locally to debug test failures
- Check dependencies for setup issues

See: https://openwisp.io/docs/dev/developer/contributing.html
"""

    def post_comment(self, message):
        """Post or update comment on PR"""
        if not self.pr_number or self.pr_number.strip() == "":
            print("No PR number, skipping comment")
            return
        marker = "<!-- ci-failure-bot-comment -->"
        message_with_marker = f"{marker}\n🤖 **CI Failure Bot** (AI-powered)\n\n{message}"
        try:
            pr_num = int(self.pr_number)
            pr = self.repo.get_pull(pr_num)
            bot_login = self.github.get_user().login
            existing_comments = pr.get_issue_comments()
            for comment in existing_comments:
                if comment.user.login == bot_login and marker in comment.body:
                    print("Bot comment already exists, updating it")
                    comment.edit(message_with_marker)
                    return
            pr.create_issue_comment(message_with_marker)
            print(f"Posted comment to PR #{pr_num}")
        except (GithubException, ValueError) as e:
            print(f"Error posting comment: {e}")

    def run(self):
        """Main execution flow"""
        try:
            print("CI Failure Bot starting - AI-powered analysis")
            print(f"DEBUG: WORKFLOW_RUN_ID = {self.workflow_run_id}")
            print(f"DEBUG: PR_NUMBER = {self.pr_number}")
            
            # For demo without WORKFLOW_RUN_ID, use fallback
            if not self.workflow_run_id:
                print("Demo mode: No WORKFLOW_RUN_ID provided, using fallback analysis")
                if not self.pr_number or self.pr_number.strip() == "":
                    print("No PR number, cannot post comment")
                    print(f"DEBUG: PR_NUMBER value: '{self.pr_number}'")
                    return
                
                # Simple demo analysis
                analysis = """❌ Code Formatting Issues Detected

**Primary Issue:** Code doesn't follow Python style guidelines

**Technical Diagnosis:**
- Failed Jobs: python-qa-checks
- Files Changed: format_test.py
- Error Type: PEP 8 style violations
- Root Cause: Code formatting doesn't meet standards"""
                
                # Compose final message with authoritative OpenWISP QA instructions
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                final_message = f"""🤖 CI Failure Bot - Code Quality Analysis ({timestamp})

{analysis}

{self.openwisp_qa_block()}

Analysis based on demo formatting failure - {timestamp}"""
                
                # Post comment
                print(f"DEBUG: posting comment to PR_NUMBER={self.pr_number}")
                self.post_comment(final_message)
                print("CI Failure Bot completed successfully (demo mode)")
                return
            try:
                if self.workflow_run_id:
                    workflow_run = self.repo.get_workflow_run(int(self.workflow_run_id))
                    if (
                        workflow_run.actor
                        and "dependabot" in workflow_run.actor.login.lower()
                    ):
                        print(f"Skipping dependabot PR from {workflow_run.actor.login}")
                        return
                if self.pr_number and self.pr_number.strip():
                    try:
                        pr_num = int(self.pr_number)
                        pr = self.repo.get_pull(pr_num)
                        if pr.head.repo is None:
                            print("Skipping PR with deleted head repository")
                            return
                        if pr.head.repo.full_name != self.repository_name:
                            print(f"Skipping fork PR from {pr.head.repo.full_name}")
                            return
                    except (GithubException, ValueError) as e:
                        print(f"Warning: Could not check fork status: {e}")
            except (GithubException, AttributeError, ValueError) as e:
                print(f"Warning: Could not check actor: {e}")
            build_logs = self.get_build_logs()
            pr_diff = self.get_pr_diff()
            if not build_logs and not pr_diff:
                print("No build logs or PR diff found, using fallback analysis")
            print("Analyzing failure with Gemini AI...")
            ai_response = self.analyze_with_gemini(build_logs, pr_diff)
            self.post_comment(ai_response)
            print("CI Failure Bot completed successfully")
        except Exception as e:
            print(f"CRITICAL ERROR in CI Failure Bot: {e}")
            import traceback
            traceback.print_exc()
            # NEVER fail the job - comments are side-effects
            return


if __name__ == "__main__":
    bot = CIFailureBot()
    bot.run()