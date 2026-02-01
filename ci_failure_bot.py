#!/usr/bin/env python3
"""CI Failure Bot - AI-powered analysis of build failures using Gemini"""

import io
import json
import os
import re
import sys
import zipfile

import google.generativeai as genai
import requests
from github import Github, GithubException


def strip_required_actions(text: str) -> str:
    """
    Remove ANY 'Required Actions' section produced by Gemini.
    """
    pattern = r"\*\*Required Actions:\*\*.*?(?=\n\*\*|\Z)"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip()


class CIFailureBot:
    def __init__(self):
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.workflow_run_id = os.environ.get("WORKFLOW_RUN_ID")
        self.repository_name = os.environ.get("REPOSITORY")
        self.pr_number = os.environ.get("PR_NUMBER")
        if not all(
            [
                self.github_token,
                self.workflow_run_id,
                self.repository_name,
            ]
        ):
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
        # Initialize Gemini client with new API (optional)
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
            self.model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
            self.model = genai.GenerativeModel(self.model_name)
        else:
            print("Warning: GEMINI_API_KEY not provided, will use fallback responses")
            self.model = None

    def get_build_logs(self):
        """Get actual build logs and error output from failed jobs"""
        try:
            workflow_run = self.repo.get_workflow_run(self.workflow_run_id)
            jobs = workflow_run.jobs()
            build_logs = []
            for job in jobs:
                if job.conclusion == "failure":
                    # Get job logs URL and fetch content
                    logs_url = job.logs_url
                    if logs_url:
                        headers = {
                            "Authorization": f"token {self.github_token}",
                            "Accept": "application/vnd.github.v3+json",
                        }
                        response = requests.get(logs_url, headers=headers, timeout=30)
                        response.raise_for_status()
                        # Handle ZIP archive response from GitHub Actions logs API
                        raw = response.content
                        if raw[:2] == b"PK":  # ZIP file signature
                            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                                parts = []
                                for name in zf.namelist():
                                    if name.endswith(".txt"):
                                        parts.append(
                                            zf.read(name).decode("utf-8", "replace")
                                        )
                                log_text = "\n".join(parts).strip()
                        else:
                            log_text = raw.decode("utf-8", "replace")
                        if len(log_text) > 5000:
                            # Take first 2000 and last 3000 chars for better context
                            log_text = (
                                log_text[:2000]
                                + "\n\n[...middle truncated...]\n\n"
                                + log_text[-3000:]
                            )
                        build_logs.append(
                            {
                                "job_name": job.name,
                                "logs": log_text,
                            }
                        )
                    # Also get step details
                    for step in job.steps:
                        if step.conclusion == "failure":
                            build_logs.append(
                                {
                                    "job_name": job.name,
                                    "step_name": step.name,
                                    "step_number": step.number,
                                }
                            )
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
            # Use git diff instead of HTTP request for efficiency
            try:
                import subprocess

                # Validate branch name to prevent injection
                default_branch = self.repo.default_branch
                if (
                    not default_branch
                    or not default_branch.replace("-", "")
                    .replace("_", "")
                    .replace("/", "")
                    .isalnum()
                ):
                    raise ValueError("Invalid branch name")
                result = subprocess.run(
                    ["git", "diff", f"origin/{default_branch}"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0 and result.stdout.strip():
                    diff_text = result.stdout
                else:
                    # Fallback to HTTP if git diff fails or returns empty
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
            except (subprocess.SubprocessError, FileNotFoundError, ValueError):
                # Fallback to HTTP if git is not available
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
            # Filter out deleted files from diff to avoid analyzing removed code
            filtered_lines = []
            skip_deleted_file = False
            for line in diff_text.split('\n'):
                if line.startswith('diff --git'):
                    # Check if this is a deleted file
                    skip_deleted_file = False
                elif line.startswith('deleted file mode'):
                    skip_deleted_file = True
                elif line.startswith('diff --git') or not skip_deleted_file:
                    filtered_lines.append(line)
            
            diff_text = '\n'.join(filtered_lines)
            
            if len(diff_text) > 8000:
                # Take first 4000 and last 4000 chars for context
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

    def get_workflow_yaml(self):
        """Get the workflow YAML configuration"""
        try:
            workflow_run = self.repo.get_workflow_run(self.workflow_run_id)
            workflow_path = workflow_run.path
            # Get workflow file content from the commit that ran
            workflow_file = self.repo.get_contents(
                workflow_path, ref=workflow_run.head_sha
            )
            return workflow_file.decoded_content.decode("utf-8")
        except GithubException as e:
            print(f"Error getting workflow YAML: {e}")
            return None

    def analyze_with_gemini(self, build_logs, pr_diff, workflow_yaml):
        """Send context to Gemini for intelligent analysis"""
        # Prepare context for Gemini
        project_name = self.repository_name.split("/")[-1]
        repo_url = f"https://github.com/{self.repository_name}"
        # Use dynamic branch detection instead of hardcoded "master"
        default_branch = self.repo.default_branch
        qa_checks_url = f"{repo_url}/blob/{default_branch}/openwisp-qa-check"
        runtests_url = f"{repo_url}/blob/{default_branch}/runtests"
        # Build the context string with proper line breaks
        build_logs_json = json.dumps(build_logs, indent=2)
        if pr_diff:
            pr_diff_json = json.dumps(pr_diff, indent=2)
        else:
            pr_diff_json = "No PR associated"
        # Gemini prompt - DIAGNOSIS ONLY, NO COMMANDS
        context = f"""
### ROLE
You are a CI failure analyst. Your job is to explain WHY the build failed, not HOW to fix it.

### INPUT CONTEXT PROVIDED
1. **Build Output/Logs:** {build_logs_json}
2. **YAML Workflow:** {workflow_yaml or "Not available"}
3. **PR Diff:** {pr_diff_json}
4. **Project Name:** {project_name}
5. **Repository:** {repo_url}

### TASK
Analyze the provided context and explain the failure. Be direct and technical.

### RESPONSE FORMAT
Provide a clear diagnosis in this format:

**Primary Issue:** [One sentence summary]

**Technical Diagnosis:**
- Failed Jobs: [job names]
- Files Changed: [file names]
- Error Type: [type of error]
- Root Cause: [why it failed]

### CRITICAL RULE
DO NOT include any commands, tools, or fix instructions. Only explain the failure and its cause.

Analyze the failure and provide your diagnosis:
"""
        try:
            # Check if Gemini is available
            if not self.model:
                return self.fallback_response()
            # Use Gemini client API
            response = self.model.generate_content(context)
            return response.text
        except (ValueError, ConnectionError, Exception) as e:
            print(f"Error calling Gemini API: {e}")
            return self.fallback_response()

    def openwisp_qa_block(self):
        return """
**Required Actions:**
- Install QA tools: `pip install -e .[qa]`
- Run `./run-qa-checks` to see all issues
- Run `openwisp-qa-format` to automatically fix formatting
- Run `./runtests` locally to verify all tests pass
"""

    def fallback_response(self):
        """Fallback response if Gemini fails"""
        return """
## CI Build Failed

The automated analysis is temporarily unavailable. Please check the CI logs above for specific error details.

**OpenWISP QA Workflow:**
1. Install QA tools: `pip install -e .[qa]`
2. Run `./run-qa-checks` to see all issues
3. Run `openwisp-qa-format` to automatically fix formatting
4. Run `./runtests` locally to verify all tests pass

**Common Issues:**
- Code style violations detected by OpenWISP QA checks
- Missing or failing tests
- Import/dependency problems

See: https://openwisp.io/docs/dev/developer/contributing.html
"""

    def post_comment(self, message):
        """Post or update comment on PR"""
        if not self.pr_number or self.pr_number.strip() == "":
            print("No PR number, skipping comment")
            return
        # Add consistent marker for deduplication
        marker = "<!-- ci-failure-bot-comment -->"
        message_with_marker = f"{marker}\n{message}"
        try:
            pr_num = int(self.pr_number)
            pr = self.repo.get_pull(pr_num)
            # Check for existing bot comments to avoid duplicates
            bot_login = self.github.get_user().login
            existing_comments = pr.get_issue_comments()
            for comment in existing_comments:
                if comment.user.login == bot_login and marker in comment.body:
                    print("Bot comment already exists, updating it")
                    comment.edit(message_with_marker)
                    return
            # No existing comment, create new one
            pr.create_issue_comment(message_with_marker)
            print(f"Posted comment to PR #{pr_num}")
        except (GithubException, ValueError) as e:
            print(f"Error posting comment: {e}")

    def run(self):
        """Main execution flow"""
        try:
            print("CI Failure Bot starting - AI-powered analysis")
            # Security checks: Skip if this is a dependabot PR or fork PR
            try:
                workflow_run = self.repo.get_workflow_run(self.workflow_run_id)
                if (
                    workflow_run.actor
                    and "dependabot" in workflow_run.actor.login.lower()
                ):
                    print(f"Skipping dependabot PR from {workflow_run.actor.login}")
                    return
                # Skip fork PRs for security (avoid sending external code to AI)
                if self.pr_number and self.pr_number.strip():
                    try:
                        pr_num = int(self.pr_number)
                        pr = self.repo.get_pull(pr_num)
                        # Handle deleted fork repositories
                        if pr.head.repo is None:
                            print("Skipping PR with deleted head repository")
                            return
                        if pr.head.repo.full_name != self.repository_name:
                            print(f"Skipping fork PR from {pr.head.repo.full_name}")
                            return
                    except (GithubException, ValueError) as e:
                        print(f"Warning: Could not check fork status: {e}")
            except (GithubException, AttributeError) as e:
                print(f"Warning: Could not check actor: {e}")
            # Get all context
            build_logs = self.get_build_logs()
            pr_diff = self.get_pr_diff()
            workflow_yaml = self.get_workflow_yaml()
            if not build_logs:
                print("No build logs found")
                return
            print("Analyzing failure with Gemini AI...")
            # Get AI analysis (diagnosis only)
            analysis = self.analyze_with_gemini(build_logs, pr_diff, workflow_yaml)
            
            # 🚫 Strip Gemini's Required Actions completely
            analysis = strip_required_actions(analysis)
            
            # Compose final message with authoritative OpenWISP QA instructions
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            final_message = f"""🤖 CI Failure Bot - Code Quality Analysis ({timestamp})

{analysis}

{self.openwisp_qa_block()}

Analysis based on actual job failures - {timestamp}"""
            
            # Post intelligent comment
            self.post_comment(final_message)
            print("CI Failure Bot completed successfully")
        except Exception as e:
            print(f"CRITICAL ERROR in CI Failure Bot: {e}")
            print(f"Error type: {type(e).__name__}")
            import traceback

            traceback.print_exc()
            sys.exit(1)


def main():
    """Entry point for the CI failure bot"""
    try:
        bot = CIFailureBot()
        bot.run()
    except Exception as e:
        print(f"FATAL: CI Failure Bot crashed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
