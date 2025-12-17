#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

MAIN_REPO = Path.home() / "dev" / "academic-profile"
SITE_DIR = MAIN_REPO / "site"
GHPAGES_WORKTREE = Path.home() / "dev" / "academic-profile-ghpages"

def run(cmd, cwd=None):
    print(f"\n→ ({cwd or '.'}) $ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)

def git_has_changes(repo_dir: Path) -> bool:
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(r.stdout.strip())

def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else "Update site"

    # 1) Commit + push main (if anything changed)
    run(["git", "switch", "main"], cwd=MAIN_REPO)

    if git_has_changes(MAIN_REPO):
        run(["git", "add", "-A"], cwd=MAIN_REPO)
        run(["git", "commit", "-m", msg], cwd=MAIN_REPO)
    else:
        print("\n(no changes to commit on main)")

    run(["git", "push", "origin", "main"], cwd=MAIN_REPO)

    # 2) Render Quarto
    run(["quarto", "render"], cwd=SITE_DIR)

    # 3) Deploy to gh-pages worktree
    run(["git", "switch", "gh-pages"], cwd=GHPAGES_WORKTREE)

    # Clean tracked files safely
    run(["git", "rm", "-r", "--quiet", "."], cwd=GHPAGES_WORKTREE)

    # Copy rendered site into gh-pages root
    run(["bash", "-lc", f'cp -R "{SITE_DIR / "_site"}"/* "{GHPAGES_WORKTREE}/"'], cwd=GHPAGES_WORKTREE)

    # Ensure nojekyll
    (GHPAGES_WORKTREE / ".nojekyll").touch()

    run(["git", "add", "-A"], cwd=GHPAGES_WORKTREE)

    # Commit only if there are changes
    if git_has_changes(GHPAGES_WORKTREE):
        run(["git", "commit", "-m", "Deploy site"], cwd=GHPAGES_WORKTREE)
    else:
        print("\n(no changes to deploy on gh-pages)")

    # Force-with-lease to handle non-fast-forward deploy updates safely
    run(["git", "push", "--force-with-lease", "origin", "gh-pages"], cwd=GHPAGES_WORKTREE)

    print("\n✅ Done. Hard refresh https://npsweeney.co.uk (Cmd+Shift+R).")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print("\n❌ Command failed:", e, file=sys.stderr)
        sys.exit(e.returncode)
