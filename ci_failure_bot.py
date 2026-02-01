import os
from github import Github

def main():
    token = os.environ.get("GITHUB_TOKEN")
    repo_name = os.environ.get("REPOSITORY")
    pr_number = os.environ.get("PR_NUMBER")
    
    print("DEBUG token:", bool(token))
    print("DEBUG repo:", repo_name)
    print("DEBUG pr:", pr_number)
    
    if not all([token, repo_name, pr_number]):
        print("Missing env vars, exiting")
        return
    
    gh = Github(token)
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(int(pr_number))
    
    body = """🤖 **CI Failure Bot**

❌ **Code Formatting Issues Detected**

**Required Actions:**
- Install QA tools: `pip install -e .[qa]`
- Run `./run-qa-checks` to see all issues
- Run `openwisp-qa-format` to automatically fix formatting
- Run `./runtests` locally to verify all tests pass

_This is a demo message from the OpenWISP CI failure bot._
"""
    
    pr.create_issue_comment(body)
    print("✅ Comment posted successfully")

if __name__ == "__main__":
    main()