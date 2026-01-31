#!/usr/bin/env python3
"""CI Failure Bot - AI-powered analysis of build failures using Gemini"""

import io
import json
import os
import sys
import zipfile

import requests
from github import Github, GithubException
from google import genai


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

                result = subprocess.run(
                    ["git", "diff", f"origin/{self.repo.default_branch}"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    diff_text = result.stdout
                else:
                    # Fallback to HTTP if git diff fails
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
        # Build the context string with proper line breaks
        build_logs_json = json.dumps(build_logs, indent=2)
        if pr_diff:
            pr_diff_json = json.dumps(pr_diff, indent=2)
        else:
            pr_diff_json = "No PR associated"

        # Gemini prompt for demo repository
        context = f"""
### ROLE
You are an AI-powered CI failure analysis bot. Analyze the build failure and provide helpful feedback.

### INPUT CONTEXT PROVIDED
1. **Build Output/Logs:** {build_logs_json}
2. **YAML Workflow:** {workflow_yaml or "Not available"}
3. **PR Diff:** {pr_diff_json}
4. **Project Name:** {project_name}
5. **Repository:** {repo_url}

### TASK
Analyze the provided context to determine why the build failed and provide specific guidance.

### RESPONSE STRUCTURE
1. **Status Summary:** Brief assessment of the failure type
2. **Technical Diagnosis:** Identify specific errors and why they occurred
3. **Required Actions:** Provide exact commands or steps to fix
4. **Root Cause:** Explain the underlying issue

Analyze the failure and provide your response:
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

    def fallback_response(self):
        """Fallback response if Gemini fails"""
        return """
## CI Build Failed

The automated analysis is temporarily unavailable. Please check the CI logs above for specific error details.

Common fixes:
- Run formatting tools: `black .` and `isort .`
- Run tests locally: `python -m pytest -v`
- Check for import errors and missing dependencies

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
            # Get all context
            build_logs = self.get_build_logs()
            pr_diff = self.get_pr_diff()
            workflow_yaml = self.get_workflow_yaml()
            if not build_logs:
                print("No build logs found")
                return
            print("Analyzing failure with Gemini AI...")
            # Get AI analysis
            ai_response = self.analyze_with_gemini(build_logs, pr_diff, workflow_yaml)
            # Post intelligent comment
            self.post_comment(ai_response)
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