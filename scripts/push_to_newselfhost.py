"""
push_to_newselfhost.py
Clean-push the Dailsmart codebase to https://github.com/dineshreddy8742/newselfhost
in per-directory batches so we never hit GitHub's 408 timeout.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile


def run(cmd, cwd, check=True):
    res = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and res.returncode != 0:
        print(f"CMD FAILED: {cmd}")
        print("STDOUT:", res.stdout)
        print("STDERR:", res.stderr)
        sys.exit(1)
    return res


def push_in_batches():
    source_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_repo = "https://github.com/dineshreddy8742/newselfhost.git"

    exclude_dirs = {
        '.git', '.git.old', '.github', '.vscode', 'node_modules',
        '__pycache__', '.next', '.pytest_cache', 'dist', 'build', 'venv', '.venv',
        'dograh_pcm_cache', 'brain', '.agents', 'pipecat',
    }
    exclude_files = {
        'deploy.zip', 'deploy_all.zip', 'deploy_code.tar.gz', 'deploy_modified.zip',
        'dump.sql', 'backup_data.sql', 'cloud-sql-proxy.exe', 'image.png',
        'pipecat.tar.gz', 'gcp-key.json', '.env',
    }

    temp_dir = os.path.join(tempfile.gettempdir(), "newselfhost_clean")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
    os.makedirs(temp_dir, exist_ok=True)

    # --- 1. Copy source files ---
    print("1. Copying project files to:", temp_dir)
    for item in os.listdir(source_dir):
        if item in exclude_dirs or item in exclude_files:
            continue
        src = os.path.join(source_dir, item)
        dst = os.path.join(temp_dir, item)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
        elif os.path.isdir(src):
            shutil.copytree(
                src, dst,
                ignore=shutil.ignore_patterns(
                    '.git', '.git*', 'node_modules', '__pycache__',
                    '.next', '*.pyc', '*.tmp', '*.log', '.pytest_cache',
                    '.env', '.env.*', '*.env',
                )
            )

    # --- 2. Init fresh repo (no pull / reset – we own main) ---
    print("2. Initialising clean git repo...")
    run(["git", "init"], temp_dir)
    run(["git", "config", "user.name",  "dineshreddy8742"], temp_dir)
    run(["git", "config", "user.email", "palavaladineshkumarreddy17@gmail.com"], temp_dir)
    run(["git", "config", "http.postBuffer", "524288000"], temp_dir)
    run(["git", "config", "core.autocrlf", "false"], temp_dir)
    run(["git", "branch", "-M", "main"], temp_dir)
    run(["git", "remote", "add", "origin", target_repo], temp_dir)

    # Fetch so we can create a commit on top of the existing README
    print("3. Fetching remote...")
    run(["git", "fetch", "origin"], temp_dir, check=False)
    # Merge remote README into our working tree (without clobbering our files)
    run(["git", "checkout", "-b", "incoming", "origin/main"], temp_dir, check=False)
    run(["git", "checkout", "main"], temp_dir, check=False)
    # Merge the remote README commit so push doesn't get "rejected non-fast-forward"
    run(["git", "merge", "--allow-unrelated-histories", "-X", "ours", "incoming", "-m", "Merge remote README"], temp_dir, check=False)

    # --- helper: add a list of paths, commit, push ---
    def commit_and_push(label, paths):
        any_added = False
        for p in paths:
            full = os.path.join(temp_dir, p)
            if os.path.exists(full):
                run(["git", "add", "-f", p], temp_dir)
                any_added = True
        if not any_added:
            print(f"  [--] nothing to add for batch: {label}")
            return
        status = run(["git", "status", "--porcelain"], temp_dir).stdout.strip()
        if status:
            run(["git", "commit", "-m", f"Add {label}"], temp_dir)
            res = run(["git", "push", "--force", "origin", "main"], temp_dir, check=False)
            if res.returncode != 0:
                print(f"PUSH FAILED for '{label}':\n{res.stderr}")
                sys.exit(1)
            print(f"  [OK] pushed: {label}")
        else:
            print(f"  [--] nothing new for batch: {label}")

    # Batch 1 - root files + scripts / deploy / config / nginx / db-migrate
    print("4. Pushing root files and scripts...")
    root_files = [
        f for f in os.listdir(temp_dir)
        if os.path.isfile(os.path.join(temp_dir, f)) and f != 'README.md'
    ]
    commit_and_push(
        "root configs and scripts",
        root_files + ['scripts', 'deploy', 'config', 'nginx', 'db-migrate']
    )

    # Batch 2 - API backend
    print("5. Pushing API backend...")
    commit_and_push("FastAPI backend (api/)", ['api'])

    # Batch 3 - UI frontend
    print("6. Pushing Next.js UI...")
    commit_and_push("Next.js frontend (ui/)", ['ui'])

    # Batch 4 - everything else
    print("7. Pushing remaining directories...")
    already_done = {'api', 'ui', 'scripts', 'deploy', 'config', 'nginx', 'db-migrate', '.git'}
    remaining = [
        d for d in os.listdir(temp_dir)
        if os.path.isdir(os.path.join(temp_dir, d)) and d not in already_done
    ]
    if remaining:
        commit_and_push("supplementary assets", remaining)

    print("\nALL DONE - code pushed to https://github.com/dineshreddy8742/newselfhost")


if __name__ == "__main__":
    push_in_batches()
