#!/usr/bin/env python3
"""Simple CI Failure Bot that works without workflow dependencies"""
import os
import sys
from github import Github
import google.generativeai as genai

def main():
    try:
        print("🤖 CI Failure Bot starting...")
        
        # Get environment variables
        github_token = os.environ.get("GITHUB_TOKEN")
        repository = os.environ.get("REPOSITORY")
        pr_number = os.environ.get("PR_NUMBER")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        
        if not all([github_token, repository, pr_number]):
            print("❌ Missing required environment variables")
            return
            
        print(f"📋 Analyzing {repository} PR #{pr_number}")
        
        # Connect to GitHub
        github = Github(github_token)
        repo = github.get_repo(repository)
        pr = repo.get_pull(int(pr_number))
        
        print(f"✅ Connected to PR: {pr.title}")
        
        # Get PR files to analyze
        files = pr.get_files()
        python_files = [f for f in files if f.filename.endswith('.py')]
        
        if python_files:
            print(f"🔍 Found {len(python_files)} Python files to analyze")
            
            # Analyze with Gemini if available
            if gemini_key:
                print("🧠 Analyzing with Gemini AI...")
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.5-flash")
                
                file_contents = []
                for file in python_files[:3]:  # Limit to first 3 files
                    if file.patch:  # Only analyze changed files
                        file_contents.append(f"File: {file.filename}\nChanges:\n{file.patch}")
                
                context = f"""
### ROLE
You are an automated maintainer analyzing a failed CI build for an OpenWISP project.

### CONTEXT
- Repository: {repository}
- PR: #{pr_number} - {pr.title}
- Files changed: {[f.filename for f in python_files]}

### FILE CHANGES
{chr(10).join(file_contents[:2000])}  

### TASK
Analyze this PR and provide direct, actionable feedback following OpenWISP standards.
The build likely failed due to code quality issues (flake8, black, isort violations).

### RESPONSE STRUCTURE
1. **Status Summary:** One sentence explaining what failed
2. **Technical Diagnosis:** Specific errors found in the code
3. **Required Actions:** Exact commands to fix issues

### TONE
Direct, technical, no fluff. Provide exact commands to fix issues.

Analyze the code quality issues:
"""
                
                try:
                    response = model.generate_content(context)
                    ai_analysis = response.text
                    print("✅ Gemini analysis completed")
                except Exception as e:
                    print(f"⚠️ Gemini API error: {e}")
                    ai_analysis = None
            else:
                ai_analysis = None
        
        # Create message
        if ai_analysis:
            message = f"""<!-- ci-failure-bot-comment -->
🤖 **CI Failure Bot** (AI-powered)

{ai_analysis}

---
*Automated analysis powered by Gemini AI*
"""
        else:
            message = """<!-- ci-failure-bot-comment -->
🤖 **CI Failure Bot** (AI-powered)

## CI Build Failed - Code Quality Issues

**Status Summary:** The build failed due to Python code formatting violations.

**Technical Diagnosis:**
- **flake8 violations**: Code style doesn't follow PEP 8 standards
- **black formatting**: Code needs automatic formatting
- **isort issues**: Import statements need proper sorting
- **Line length**: Lines exceed 88 character limit

**Required Actions:**
```bash
# Install formatting tools
pip install black flake8 isort

# Fix all formatting issues
black .
isort .

# Check for remaining issues
flake8 . --max-line-length=88 --extend-ignore=E203,W503
```

**Next Steps:**
1. Run the formatting commands above
2. Commit the changes: `git add . && git commit -m "Fix code formatting"`
3. Push to retrigger CI checks

We prioritize high-quality, ready-to-merge code. Please ensure all QA checks pass before requesting review.
"""
        
        # Post or update comment
        marker = "<!-- ci-failure-bot-comment -->"
        bot_login = github.get_user().login
        existing_comments = pr.get_issue_comments()
        
        # Check for existing bot comment
        for comment in existing_comments:
            if comment.user.login == bot_login and marker in comment.body:
                print("📝 Updating existing bot comment")
                comment.edit(message)
                print("✅ Comment updated successfully")
                return
                
        # Create new comment
        pr.create_issue_comment(message)
        print("✅ Posted new bot comment")
        
    except Exception as e:
        print(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()