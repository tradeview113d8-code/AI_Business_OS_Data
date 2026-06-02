import time
import sys
import os
from pathlib import Path
from github import Github, Auth # Import Auth
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(override=True)

from Core.job_queue import claim_job, complete_job, fail_job
from Core.logger import log_event # Added for consistency, ensure it's in original V5.1

def get_github_repo():
    token = os.getenv('GITHUB_TOKEN')
    repo_name = os.getenv('GITHUB_REPO', 'AI_Business_OS_Data')
    owner_name = os.getenv('GITHUB_OWNER', os.getenv('GITHUB_USERNAME')) # Added owner_name

    if not token:
        raise ValueError("GITHUB_TOKEN environment variable not set.")

    # Use Auth.Token for authentication
    g = Github(auth=Auth.Token(token))
    user = g.get_user()

    if not owner_name:
        owner_name = user.login # Fallback to authenticated user's login
        os.environ['GITHUB_OWNER'] = owner_name # Set it for future uses

    try:
        repo = g.get_user(owner_name).get_repo(repo_name)
    except Exception as e:
        # If repo doesn't exist under the specified owner, try to create it if it's the authenticated user
        if owner_name == user.login:
            print(f"Repository {repo_name} not found, attempting to create...")
            repo = user.create_repo(repo_name, private=True)
        else:
            raise e
    return repo

def sync_project_files(repo):
    base_path = Path(os.getenv('PROJECT_ROOT', ROOT))

    folders = ['Core', 'Telegram', 'Workers', 'Plugins', '.github']
    root_files = ['bootstrap.py', 'mongo_indexes.py', 'seed_admin.py', 'requirements.txt', 'plugin_runner.py', 'scheduler_runner.py', 'build_zip.py', '.env.example']

    all_paths = []
    for folder in folders:
        f_path = base_path / folder
        if f_path.exists():
            all_paths.extend(list(f_path.rglob('*')))

    for rf in root_files:
        rf_path = base_path / rf
        if rf_path.exists():
            all_paths.append(rf_path)

    for file_path in all_paths:
        if file_path.is_dir() or '.git' in str(file_path): continue

        rel_path = str(file_path.relative_to(base_path))
        try:
            with open(file_path, 'rb') as f_content:
                content = f_content.read()

            try:
                existing = repo.get_contents(rel_path)
                if existing.decoded_content != content:
                    repo.update_file(rel_path, f"update {rel_path}", content, existing.sha)
                    print(f"Updated: {rel_path}")
            except Exception as e: # Catch all exceptions, not just 'Not Found'
                if "not found" in str(e).lower(): # Only create if file genuinely doesn't exist
                    repo.create_file(rel_path, f"initial {rel_path}", content)
                    print(f"Created: {rel_path}")
                else:
                    print(f"Error processing {rel_path}: {e}")

        except Exception as e:
            print(f"Skipping {rel_path} due to read/write error: {e}")

def run_worker():
    print("GitHub Comprehensive-Sync Worker active...")
    while True:
        job = claim_job("github_sync", "full_sync_worker")
        if job:
            try:
                repo = get_github_repo()
                sync_project_files(repo)
                complete_job(job['_id'])
                print(f"✅ All files synced to GitHub successfully.")
            except Exception as e:
                print(f"❌ Error in worker execution: {e}")
                log_event("github_sync", "ERROR", f"Worker failed for job {job['_id']}: {str(e)}") # Log error
                fail_job(job['_id'], str(e))
        time.sleep(10)

if __name__ == '__main__':
    run_worker()