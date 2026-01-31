#!/usr/bin/env python3
"""Simple test to verify bot can comment on PR"""
import os
import sys

# Test if we can import required modules
try:
    import requests
    print("✅ requests imported successfully")
except ImportError as e:
    print(f"❌ Failed to import requests: {e}")
    sys.exit(1)

try:
    from github import Github
    print("✅ PyGithub imported successfully")
except ImportError as e:
    print(f"❌ Failed to import PyGithub: {e}")
    sys.exit(1)

# Test environment variables
github_token = os.environ.get("GITHUB_TOKEN")
repository = os.environ.get("REPOSITORY")
pr_number = os.environ.get("PR_NUMBER")

print(f"GITHUB_TOKEN: {'✅ Set' if github_token else '❌ Missing'}")
print(f"REPOSITORY: {repository or '❌ Missing'}")
print(f"PR_NUMBER: {pr_number or '❌ Missing'}")

if not all([github_token, repository, pr_number]):
    print("❌ Missing required environment variables")
    sys.exit(1)

# Test GitHub API connection
try:
    github = Github(github_token)
    repo = github.get_repo(repository)
    pr = repo.get_pull(int(pr_number))
    print(f"✅ Successfully connected to PR #{pr_number}: {pr.title}")
    
    # Post a simple test comment
    test_message = """<!-- ci-failure-bot-comment -->
🤖 **CI Failure Bot Test** 

✅ Bot is working! This is a test comment to verify the bot can post to PRs.

**Environment Check:**
- GitHub API: ✅ Connected
- Repository: ✅ {repository}
- PR: ✅ #{pr_number}

The bot is now ready to analyze CI failures!
""".format(repository=repository, pr_number=pr_number)
    
    pr.create_issue_comment(test_message)
    print("✅ Successfully posted test comment to PR")
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

print("🎉 Bot test completed successfully!")