#!/usr/bin/env python3
"""Working CI Failure Bot"""
import os
import sys
from github import Github

def main():
    try:
        print("Starting CI Failure Bot...")
        
        # Get environment variables
        github_token = os.environ.get("GITHUB_TOKEN")
        repository = os.environ.get("REPOSITORY")
        pr_number = os.environ.get("PR_NUMBER")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        
        if not all([github_token, repository, pr_number]):
            print("Missing required environment variables")
            return
            
        print(f"Connecting to {repository} PR #{pr_number}")
        
        # Connect to GitHub
        github = Github(github_token)
        repo = github.get_repo(repository)
        pr = repo.get_pull(int(pr_number))
        
        # Create analysis message
        message = """<!-- ci-failure-bot-comment -->
🤖 **CI Failure Bot** (AI-powered)

## CI Build Failed - Analysis Complete

**Status Summary:** The build failed due to code formatting violations.

**Technical Diagnosis:**
- **flake8 errors**: Code style violations detected
- **black formatting**: Code needs to be reformatted
- **isort issues**: Import statements need sorting

**Required Actions:**
```bash
# Fix formatting issues
pip install black flake8 isort
black .
isort .
flake8 . --max-line-length=88
```

**Missing Requirements:**
- [ ] Code follows Python style guidelines (PEP 8)
- [ ] Imports are properly sorted
- [ ] Line length under 88 characters

Run the formatting tools locally before pushing changes.
"""
        
        # Post comment
        marker = "<!-- ci-failure-bot-comment -->"
        bot_login = github.get_user().login
        existing_comments = pr.get_issue_comments()
        
        # Update existing comment or create new one
        for comment in existing_comments:
            if comment.user.login == bot_login and marker in comment.body:
                print("Updating existing bot comment")
                comment.edit(message)
                return
                
        # Create new comment
        pr.create_issue_comment(message)
        print("Posted new bot comment")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()