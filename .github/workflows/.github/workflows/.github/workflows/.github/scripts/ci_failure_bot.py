#!/usr/bin/env python3
"""
Demo CI Failure Bot - Gemini-powered analysis
"""

import os
import sys
import json

import google.generativeai as genai
from github import Github


class DemoCIFailureBot:
    def __init__(self):
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.workflow_run_id = os.environ.get("WORKFLOW_RUN_ID")
        self.repository_name = os.environ.get("REPOSITORY")
        self.pr_number = os.environ.get("PR_NUMBER")

        if not all([self.github_token, self.gemini_api_key, self.workflow_run_id, self.repository_name]):
            missing = []
            if not self.github_token:
                missing.append("GITHUB_TOKEN")
            if not self.gemini_api_key:
                missing.append("GEMINI_API_KEY")
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
        
        genai.configure(api_key=self.gemini_api_key)
        self.model = genai.GenerativeModel('gemini-pro')

    def get_failure_context(self):
        """Get basic failure context for demo"""
        try:
            workflow_run = self.repo.get_workflow_run(self.workflow_run_id)
            
            context = {
                'workflow_name': workflow_run.name,
                'conclusion': workflow_run.conclusion,
                'repository': self.repository_name,
                'run_number': workflow_run.run_number
            }
            
            jobs = workflow_run.jobs()
            failed_jobs = []
            for job in jobs:
                if job.conclusion == "failure":
                    failed_jobs.append({
                        'name': job.name,
                        'conclusion': job.conclusion
                    })
            
            context['failed_jobs'] = failed_jobs
            return context
            
        except Exception as e:
            print(f"Error getting failure context: {e}")
            return None

    def analyze_with_gemini(self, context):
        """Send context to Gemini for analysis"""
        
        prompt = f"""
You are an "Automated Maintainer Gatekeeper" analyzing a CI failure.

CONTEXT:
- Repository: {context['repository']}
- Workflow: {context['workflow_name']}
- Run Number: {context['run_number']}
- Failed Jobs: {json.dumps(context['failed_jobs'], indent=2)}

TASK: Analyze this CI failure and provide direct, actionable feedback.

TONE: Direct and honest, no corporate fluff.

RESPONSE STRUCTURE:
1. Status Summary: One sentence about what failed
2. Technical Diagnosis: What likely went wrong
3. Required Action: Specific steps to fix

Provide a helpful response for the contributor:
"""

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return self.fallback_response()

    def fallback_response(self):
        """Fallback if Gemini fails"""
        return """
## CI Build Failed - Demo Bot

The build failed and AI analysis is temporarily unavailable.

**Common fixes:**
- Check the workflow logs above for specific errors
- Verify all dependencies are properly installed
- Ensure code passes local tests before pushing

This is a demo of the Gemini-powered CI failure bot.
"""

    def post_comment(self, message):
        """Post comment to PR"""
        if not self.pr_number or self.pr_number.strip() == "":
            print("No PR number, skipping comment")
            return

        try:
            pr_num = int(self.pr_number)
            pr = self.repo.get_pull(pr_num)
            
            demo_message = f"🤖 **Demo CI Failure Bot** (Gemini-powered)\n\n{message}"
            
            pr.create_issue_comment(demo_message)
            print(f"✅ Posted demo comment to PR #{pr_num}")
            
        except Exception as e:
            print(f"Error posting comment: {e}")

    def run(self):
        """Main execution"""
        print("🚀 Demo CI Failure Bot starting...")
        
        context = self.get_failure_context()
        if not context:
            print("❌ Could not get failure context")
            return
        
        print(f"📊 Analyzing failure in {context['workflow_name']}")
        
        ai_response = self.analyze_with_gemini(context)
        
        self.post_comment(ai_response)
        
        print("✅ Demo CI Failure Bot completed!")


if __name__ == "__main__":
    bot = DemoCIFailureBot()
    bot.run()
