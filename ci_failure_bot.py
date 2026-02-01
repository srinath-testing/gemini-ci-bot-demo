#!/usr/bin/env python3
"""CI Failure Bot - AI-powered analysis of build failures using Gemini"""
import io
import json
import os
import sys
import zipfile
import google.generativeai as genai
import requests
from github import Github, GithubException

class CIFailureBot:
    def __init__(self):
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.workflow_run_id = os.environ.get("WORKFLOW_RUN_ID")  # Optional
        self.repository_name = os.environ.get("REPOSITORY")
        self.pr_number = os.environ.get("PR_NUMBER")
        
        # Only require essential variables - never exit
        if not self.github_token or not self.repository_name:
            missing = []
            if not self.github_token:
                missing.append("GITHUB_TOKEN")
            if not self.repository_name:
                missing.append("REPOSITORY")
            print(f"Missing required environment variables: {', '.join(missing)}")
            self.github = None
            self.repo = None
            return
        
        self.github = Github(self.github_token)
        self.repo = self.github.get_repo(self.repository_name)
        
        # Initialize Gemini (optional - never blocks)
        if self.gemini_api_key:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.model = genai.GenerativeModel("gemini-2.5-flash")
            except Exception as e:
                print(f"Gemini initialization failed: {e}")
                self.model = None
        else:
            self.model = None

    def get_build_logs(self):
        """Get actual build logs and error output from failed jobs"""
        if not self.workflow_run_id:
            return []
        try:
            workflow_run = self.repo.get_workflow_run(int(self.workflow_run_id))
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
                            log_text = (
                                log_text[:2000]
                                + "\n\n[...middle truncated...]\n\n"
                                + log_text[-3000:]
                            )
                        build_logs.append({
                            "job_name": job.name,
                            "logs": log_text,
                        })
                    for step in job.steps:
                        if step.conclusion == "failure":
                            build_logs.append({
                                "job_name": job.name,
                                "step_name": step.name,
                                "step_number": step.number,
                            })
            return build_logs
        except Exception as e:
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
                import subprocess
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
        except Exception as e:
            print(f"Error getting PR diff: {e}")
        return None

    def analyze_with_gemini(self, build_logs, pr_diff, workflow_yaml):
        """Optional Gemini analysis - never blocks comment posting"""
        if not self.model:
            return None
        try:
            project_name = self.repository_name.split("/")[-1]
            repo_url = f"https://github.com/{self.repository_name}"
            build_logs_json = json.dumps(build_logs, indent=2)
            if pr_diff:
                pr_diff_json = json.dumps(pr_diff, indent=2)
            else:
                pr_diff_json = "No PR associated"
            
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
            response = self.model.generate_content(context)
            return response.text
        except Exception as e:
            print(f"Gemini analysis failed: {e}")
            return None

    def get_openwisp_qa_message(self):
        """Generate the standard OpenWISP QA failure message"""
        return """🤖 CI Failure Bot

❌ Code Formatting Issues Detected

**Required Actions:**
- Install QA tools: `pip install -e .[qa]`
- Run `./run-qa-checks` to see all issues
- Run `openwisp-qa-format` to automatically fix formatting
- Run `./runtests` locally to verify all tests pass

**Common Issues:**
- Code style violations detected by OpenWISP QA checks
- Missing or failing tests
- Import/dependency problems

See: https://openwisp.io/docs/dev/developer/contributing.html
"""

    def post_comment(self, message):
        """Post or update comment on PR - guaranteed to attempt posting"""
        if not self.pr_number or self.pr_number.strip() == "":
            print("No PR number, skipping comment")
            return
        if not self.github or not self.repo:
            print("GitHub not initialized, cannot post comment")
            return
        
        marker = "<!-- ci-failure-bot-comment -->"
        message_with_marker = f"{marker}\n{message}"
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
        except Exception as e:
            print(f"Error posting comment: {e}")

    def run(self):
        """Main execution flow - guaranteed to post a comment"""
        analysis = None
        
        try:
            print("CI Failure Bot starting - AI-powered analysis")
            
            # Skip dependabot PRs
            if self.workflow_run_id:
                try:
                    workflow_run = self.repo.get_workflow_run(int(self.workflow_run_id))
                    if (
                        workflow_run.actor
                        and "dependabot" in workflow_run.actor.login.lower()
                    ):
                        print(f"Skipping dependabot PR from {workflow_run.actor.login}")
                        return
                except Exception as e:
                    print(f"Could not check workflow actor: {e}")
            
            # Skip fork PRs for security
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
                except Exception as e:
                    print(f"Could not check fork status: {e}")
            
            # Try to get context (optional)
            build_logs = self.get_build_logs()
            pr_diff = self.get_pr_diff()
            workflow_yaml = None
            if self.workflow_run_id:
                try:
                    workflow_run = self.repo.get_workflow_run(int(self.workflow_run_id))
                    workflow_path = workflow_run.path
                    workflow_file = self.repo.get_contents(
                        workflow_path, ref=workflow_run.head_sha
                    )
                    workflow_yaml = workflow_file.decoded_content.decode("utf-8")
                except Exception as e:
                    print(f"Error getting workflow YAML: {e}")
            
            # Try Gemini analysis (optional)
            gemini_analysis = self.analyze_with_gemini(build_logs, pr_diff, workflow_yaml)
            
            if gemini_analysis:
                analysis = f"""{gemini_analysis}

**Required Actions:**
- Install QA tools: `pip install -e .[qa]`
- Run `./run-qa-checks` to see all issues
- Run `openwisp-qa-format` to automatically fix formatting
- Run `./runtests` locally to verify all tests pass
"""
            else:
                analysis = self.get_openwisp_qa_message()
                
        except Exception as e:
            print(f"Error in analysis: {e}")
            analysis = self.get_openwisp_qa_message()
        
        # GUARANTEED comment posting - this always runs
        self.post_comment(analysis)
        print("CI Failure Bot completed successfully")

def main():
    """Entry point for the CI failure bot"""
    try:
        bot = CIFailureBot()
        if bot.github and bot.repo:  # Only run if properly initialized
            bot.run()
        else:
            print("Bot initialization failed, cannot proceed")
    except Exception as e:
        print(f"CI Failure Bot crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()