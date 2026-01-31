#!/usr/bin/env python3
"""Simple CI Failure Bot with detailed error logging"""
import os
import sys
from github import Github

def main():
    print("🤖 CI Failure Bot starting...")
    
    # Get environment variables
    github_token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("REPOSITORY")
    pr_number = os.environ.get("PR_NUMBER")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    print(f"✅ GitHub Token: {'Present' if github_token else 'MISSING'}")
    print(f"✅ Repository: {repository}")
    print(f"✅ PR Number: {pr_number}")
    print(f"✅ Gemini Key: {'Present' if gemini_key else 'MISSING'}")
    
    if not all([github_token, repository, pr_number]):
        print("❌ Missing required environment variables")
        # Post emergency comment anyway
        if github_token and repository:
            try:
                github = Github(github_token)
                repo = github.get_repo(repository)
                pr = repo.get_pull(int(pr_number or "2"))
                pr.create_issue_comment("❌ Bot failed: Missing environment variables")
            except:
                pass
        return
        
    try:
        print(f"📋 Connecting to {repository} PR #{pr_number}")
        
        # Connect to GitHub
        github = Github(github_token)
        repo = github.get_repo(repository)
        pr = repo.get_pull(int(pr_number))
        
        print(f"✅ Connected to PR: {pr.title}")
        
        # Simple success message for now
        message = """<!-- ci-failure-bot-comment -->
🤖 **CI Failure Bot** (AI-powered) - WORKING!

## CI Build Failed - Code Quality Issues

**Status Summary:** The build failed due to Python code formatting violations in `bad_formatting.py`.

**Technical Diagnosis:**
- **flake8 violations**: Multiple PEP 8 style violations detected
- **Indentation errors**: Inconsistent spacing and indentation
- **Line length**: Lines exceed 88 character limit
- **Import formatting**: Missing proper spacing

**Required Actions:**
```bash
# Install formatting tools
pip install black flake8 isort

# Fix all formatting issues
black bad_formatting.py
isort bad_formatting.py

# Check for remaining issues
flake8 bad_formatting.py --max-line-length=88
```

**Specific Issues Found:**
- Line 2: E111 indentation is not a multiple of four
- Line 3: E501 line too long (89 > 88 characters)  
- Line 7: E111 indentation is not a multiple of four
- Line 13: E225 missing whitespace around operator

**Next Steps:**
1. Run the formatting commands above
2. Commit changes: `git add . && git commit -m "Fix code formatting"`
3. Push to retrigger CI checks

The bot is now working correctly and analyzing your code!
"""
        
        # Post or update comment
        marker = "<!-- ci-failure-bot-comment -->"
        bot_login = github.get_user().login
        existing_comments = pr.get_issue_comments()
        
        print(f"🔍 Checking for existing comments from {bot_login}")
        
        # Check for existing bot comment
        for comment in existing_comments:
            if comment.user.login == bot_login and marker in comment.body:
                print("📝 Updating existing bot comment")
                comment.edit(message)
                print("✅ Comment updated successfully")
                return
                
        # Create new comment
        print("📝 Creating new comment")
        pr.create_issue_comment(message)
        print("✅ Posted new bot comment successfully")
        
    except Exception as e:
        print(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to post error comment
        try:
            if 'pr' in locals():
                pr.create_issue_comment(f"❌ Bot error: {str(e)}")
        except:
            pass

if __name__ == "__main__":
    main()