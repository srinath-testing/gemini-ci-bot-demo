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

    def analyze_with_gemini(self, build_logs):
        """Send context to Gemini for intelligent analysis"""
        if not self.model:
            return self.fallback_response()
        build_logs_json = json.dumps(build_logs, indent=2)
        context = f"""
Analyze this CI build failure and provide specific guidance:

Build Logs: {build_logs_json}

Provide a response with:
1. Status Summary (one sentence)
2. Technical Diagnosis (specific errors found)
3. Required Actions (exact commands to fix)
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
- Run code formatting tools
- Run tests locally to debug failures
- Check dependencies for setup issues
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
            build_logs = self.get_build_logs()
            if not build_logs:
                print("No build logs found")
                return
            print("Analyzing failure with Gemini AI...")
            ai_response = self.analyze_with_gemini(build_logs)
            self.post_comment(ai_response)
            print("CI Failure Bot completed successfully")
        except Exception as e:
            print(f"CRITICAL ERROR in CI Failure Bot: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    bot = CIFailureBot()
    bot.run()