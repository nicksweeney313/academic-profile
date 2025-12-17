#!/usr/bin/env python3
import subprocess
import sys
import time
from pathlib import Path

MAIN_REPO = Path.home() / "dev" / "academic-profile"
SITE_DIR = MAIN_REPO / "site"
GHPAGES_WORKTREE = Path.home() / "dev" / "academic-profile-ghpages"
CUSTOM_DOMAIN = "npsweeney.co.uk"

def run(cmd, cwd=None, capture=False):
    print(f"\n→ ({cwd or '.'}) $ {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture,
    )

def git_has_changes(repo_dir: Path) -> bool:
    r = run(["git", "status", "--porcelain"], cwd=repo_dir, capture=True)
    return bool(r.stdout.strip())

def ensure_paths():
    for p in [MAIN_REPO, SITE_DIR, GHPAGES_WORKTREE]:
        if not p.exists():
            raise SystemExit(f"Missing expected path: {p}")

def write_cname():
    out_dir = SITE_DIR / "_site"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "CNAME").write_text(CUSTOM_DOMAIN.strip() + "\n", encoding="utf-8")

def deploy_push_with_retries(max_retries=3, sleep_seconds=1.0):
    """
    Try force-with-lease push a few times, refreshing origin/gh-pages each time.
    If it keeps failing (e.g. CI updating gh-pages concurrently), fall back to --force.
    """
    for attempt in range(1, max_retries + 1):
        try:
            # Refresh remote ref so lease isn't stale
            run(["git", "fetch", "origin", "gh-pages"], cwd=GHPAGES_WORKTREE)
            run(["git", "push", "--force-with-lease", "origin", "gh-pages"], cwd=GHPAGES_WORKTREE)
            return
        except subprocess.CalledProcessError as e:
            msg = ""
            try:
                # Try to capture stderr if possible (best-effort)
                msg = str(e)
            except Exception:
                pass

            print(f"\n⚠️ Push attempt {attempt}/{max_retries} failed (likely stale lease).")
            if attempt < max_retries:
                time.sleep(sleep_seconds)
                continue

            print("\n⚠️ Still failing after retries. Falling back to `git push --force` for gh-pages.")
            run(["git", "push", "--force", "origin", "gh-pages"], cwd=GHPAGES_WORKTREE)
            return

def main():
    ensure_paths()
    msg = sys.argv[1] if len(sys.argv) > 1 else "Update site"

    # 1) Commit + push main (if needed)
    run(["git", "switch", "main"], cwd=MAIN_REPO)

    if git_has_changes(MAIN_REPO):
        run(["git", "add", "-A"], cwd=MAIN_REPO)
        run(["git", "commit", "-m", msg], cwd=MAIN_REPO)
    else:
        print("\n(no changes to commit on main)")

    run(["git", "push", "origin", "main"], cwd=MAIN_REPO)

    # 2) Render Quarto
    run(["quarto", "render"], cwd=SITE_DIR)

    # 2.5) Ensure custom domain survives deploy
    write_cname()

    # 3) Deploy to gh-pages worktree
    run(["git", "switch", "gh-pages"], cwd=GHPAGES_WORKTREE)

    # Make sure gh-pages worktree is up to date before overwriting contents
    run(["git", "fetch", "origin", "gh-pages"], cwd=GHPAGES_WORKTREE)
    run(["git", "reset", "--hard", "origin/gh-pages"], cwd=GHPAGES_WORKTREE)

    # Clean tracked files safely
    run(["git", "rm", "-r", "--quiet", "."], cwd=GHPAGES_WORKTREE)

    # Copy rendered site into gh-pages root
    run(["bash", "-lc", f'cp -R "{SITE_DIR / "_site"}"/* "{GHPAGES_WORKTREE}/"'], cwd=GHPAGES_WORKTREE)

    # Ensure nojekyll
    (GHPAGES_WORKTREE / ".nojekyll").touch()

    run(["git", "add", "-A"], cwd=GHPAGES_WORKTREE)

    if git_has_changes(GHPAGES_WORKTREE):
        run(["git", "commit", "-m", "Deploy site"], cwd=GHPAGES_WORKTREE)
    else:
        print("\n(no changes to deploy on gh-pages)")

    deploy_push_with_retries(max_retries=3, sleep_seconds=1.0)

    print("\n✅ Done. Hard refresh https://npsweeney.co.uk (Cmd+Shift+R).")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print("\n❌ Command failed:", e, file=sys.stderr)
        sys.exit(e.returncode)
