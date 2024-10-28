import os
import shutil
import subprocess
import requests
from flask import Flask, request, jsonify
from git import Repo

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook_listener():
    # Check if a pull request is opened
    data = request.json
    if 'pull_request' in data and data['action'] == 'opened':
        pr_url = data['pull_request']['url']
        clone_and_test(pr_url)  # Trigger cloning and testing
    return jsonify({'status': 'received'}), 200

def clone_and_test(pr_url):
    # Set up GitHub repository URL with token authentication
    token = os.getenv('DJANGO_REPO_PAT')
    repo_url = f"https://{token}@github.com/rtiwari13/inventory-management-application.git"  
    repo_path = os.path.join(os.getcwd(), 'inventory-management-application')
    
    # Remove existing directory if it exists to prevent conflicts
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)  # Delete existing repository directory

    try:
        # Clone the repository into a fresh directory
        Repo.clone_from(repo_url, repo_path)
        
        # Install dependencies from requirements.txt
        subprocess.run(["pip", "install", "-r", f"{repo_path}/requirements.txt"], check=True)
    except Exception as e:
        print(f"Error during cloning or dependency installation: {e}")
        return  # Exit if there’s an error

    # Run tests and generate reports
    run_tests_and_generate_reports(repo_path)

    # Push reports to the test repository
    push_reports_to_tests_repo(repo_path)

    # Comment on the pull request with report links
    comment_on_pr(pr_url)

def run_tests_and_generate_reports(repo_path):
    # Run code coverage analysis
    subprocess.run(
    ["coverage", "run", "--source=inventory-management-application", "manage.py", "test"],
    cwd="/workspaces/pr/flask-webhook-listener/inventory-management-application/inventory",
)

    
    # Generate HTML report for coverage
    subprocess.run(["coverage", "html", "-d", f"{repo_path}/coverage_html"], check=True)

    # Run linting and save the report
    with open(f"{repo_path}/tests.html", "w") as lint_report:
        subprocess.run(["flake8", "--format=html", "--output-file=tests.html"], stdout=lint_report, cwd=repo_path, check=True)

def push_reports_to_tests_repo(repo_path):
    # Clone the GitHub repository for storing test reports
    token = os.getenv('YOUR_GITHUB_PAT')
    tests_repo_url = f"https://{token}@github.com/kartikvermaa/tests-repo.git"
    tests_repo_path = "/workspace/tests-repo"
    
    # Remove existing directory if it exists
    if os.path.exists(tests_repo_path):
        shutil.rmtree(tests_repo_path)

    # Clone the tests repository
    Repo.clone_from(tests_repo_url, tests_repo_path)

    # Copy generated HTML reports to the tests repository
    shutil.copy(f"{repo_path}/coverage_html/index.html", f"{tests_repo_path}/index.html")
    shutil.copy(f"{repo_path}/tests.html", f"{tests_repo_path}/tests.html")

    # Commit and push the updated reports
    repo = Repo(tests_repo_path)
    repo.git.add(update=True)
    repo.index.commit("Update test and coverage reports")
    origin = repo.remote(name='origin')
    origin.push()

def comment_on_pr(pr_url):
    # Set up report URLs on GitHub Pages
    gh_pages_base_url = "https://kartikvermaa.github.io/tests-repo"
    coverage_url = f"{gh_pages_base_url}/index.html"
    linting_url = f"{gh_pages_base_url}/tests.html"

    # Headers for GitHub API authorization
    headers = {
        "Authorization": f"token {os.getenv('YOUR_GITHUB_PAT')}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    # Comment content with report links
    comment_body = {
        "body": f"### Test Reports\n- [Code Coverage Report]({coverage_url})\n- [Linting Report]({linting_url})"
    }
    
    # Post comment on the pull request
    response = requests.post(f"{pr_url}/comments", json=comment_body, headers=headers)
    if response.status_code == 201:
        print("Comment posted successfully.")
    else:
        print("Failed to post comment.")

if __name__ == '__main__':
    # Start the Flask server
    app.run(host='0.0.0.0', port=5000)
