#!/usr/bin/env python3
import os
from github import Github

# Direct test - no complexity
github_token = os.environ.get("GITHUB_TOKEN")
repository = "srinath-testing/gemini-ci-bot-demo"
pr_number = "2"

print(f"Token exists: {bool(github_token)}")
print(f"Repository: {repository}")
print(f"PR: {pr_number}")

try:
    github = Github(github_token)
    repo = github.get_repo(repository)
    pr = repo.get_pull(int(pr_number))
    
    message = """<!-- ci-failure-bot-comment -->
🤖 **EMERGENCY TEST** 

This is a direct test to verify the bot can comment. If you see this, the bot infrastructure works!

Time: """ + str(__import__('datetime').datetime.now())
    
    pr.create_issue_comment(message)
    print("SUCCESS: Comment posted!")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()