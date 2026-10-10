#!/usr/bin/env python3
"""Is a site's existing deploy connected and current?

Revision check (GitHub only, no server access):
    deploy_check.py revision --repo a8cteam51/site --branch trunk --deployed-rev <sha>

Drift check (compares files on the server with the deployed revision):
    deploy_check.py drift --repo a8cteam51/site --rev <sha> --host pressable --site example.com
    deploy_check.py drift --repo-dir /path/to/clone --rev <sha> --host pressable --site example.com

Both print JSON. Both are read-only. A repo existing for a site proves nothing:
only run these for a DeployHQ server (or host deployment) that is confirmed to
target the site being audited.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd, cwd=None, env=None, check=True):
    res = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError("%s failed: %s" % (" ".join(cmd[:4]), (res.stderr or res.stdout).strip()[-400:]))
    return res.stdout


TOOLING_NAMES = ("LICENSE", "composer.json", "composer.lock", "package.json", "package-lock.json", "phpcs.xml", ".editorconfig",
                 "Makefile", "gulpfile.js", "postcss.config.js", "webpack.config.js")


def is_tooling(path):
    """Repo files that a wp-content deploy never puts on the server.

    Root level only. A readme, config file or dotfile inside a theme or plugin
    is deployed with it, so it is compared like any other file.
    """
    top = path.split("/", 1)[0]
    if top.startswith("."):
        return True
    return "/" not in path and (path.lower().endswith((".md", ".yml", ".yaml")) or path in TOOLING_NAMES)


def revision(args):
    head = json.loads(run(["gh", "api", "repos/%s/commits/%s" % (args.repo, args.branch)]))
    head_sha = head["sha"]
    out = {"repo": args.repo, "branch": args.branch, "deployed_rev": args.deployed_rev, "branch_head": head_sha,
           "branch_head_date": head["commit"]["committer"]["date"]}
    if head_sha.startswith(args.deployed_rev) or args.deployed_rev.startswith(head_sha):
        out.update(state="current", undeployed_commits=[])
    else:
        try:
            cmp_ = json.loads(run(["gh", "api", "repos/%s/compare/%s...%s" % (args.repo, args.deployed_rev, head_sha)]))
            out["ahead_by"] = cmp_["ahead_by"]
            out["behind_by"] = cmp_["behind_by"]
            out["undeployed_commits"] = [
                {"sha": c["sha"][:12], "date": c["commit"]["committer"]["date"], "author": c["commit"]["author"]["name"],
                 "message": c["commit"]["message"].splitlines()[0][:120]} for c in cmp_["commits"]][:40]
            out["files_changed"] = [f["filename"] for f in cmp_.get("files", [])][:80]
            # Commits that only touch repo tooling never reach the server, so they are not a deploy gap.
            deployable = [f for f in out["files_changed"] if not is_tooling(f)]
            out["deployable_files_changed"] = deployable
            if cmp_["behind_by"] != 0:
                out["state"] = "diverged"
            else:
                out["state"] = "behind" if deployable else "behind-tooling-only"
        except RuntimeError as err:
            out.update(state="unknown", error=str(err))
    json.dump(out, sys.stdout, indent=2)
    print()


def load_ignore(repo_dir, rev):
    try:
        text = run(["git", "show", "%s:.deployignore" % rev], cwd=repo_dir)
    except RuntimeError:
        return []
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


def ignored(path, patterns):
    base = os.path.basename(path)
    for pat in patterns:
        bare = pat.strip("/")
        if pat.endswith("/**"):
            bare = pat[:-3].strip("/")
        if path == bare or path.startswith(bare + "/") or fnmatch.fnmatch(path, pat.lstrip("/")) or fnmatch.fnmatch(base, pat.replace("**/", "")):
            return True
    return False


def drift(args):
    tmp = None
    try:
        repo_dir = args.repo_dir
        if not repo_dir:
            tmp = tempfile.mkdtemp(prefix="t51-drift-")
            run(["gh", "repo", "clone", args.repo, tmp, "--", "--quiet", "--no-checkout"])
            repo_dir = tmp
        _drift(args, repo_dir)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def _drift(args, repo_dir):
    try:
        run(["git", "cat-file", "-e", args.rev + "^{commit}"], cwd=repo_dir)
    except RuntimeError:
        run(["git", "fetch", "--quiet", "origin", args.rev], cwd=repo_dir)

    patterns = load_ignore(repo_dir, args.rev)
    tracked = [p for p in run(["git", "ls-tree", "-r", "--name-only", args.rev], cwd=repo_dir).splitlines() if p]
    deployable = [p for p in tracked if not ignored(p, patterns) and not is_tooling(p)]

    # Compare whole directories for our own themes and plugins, single files elsewhere
    # (mu-plugins also holds host files that are not ours to judge).
    roots, singles = set(), set()
    for p in deployable:
        parts = p.split("/")
        if parts[0] in ("themes", "plugins") and len(parts) > 2:
            roots.add("/".join(parts[:2]))
        elif parts[0] == "mu-plugins" and len(parts) > 2:
            roots.add("/".join(parts[:2]))
        else:
            singles.add(p)

    env = dict(os.environ, T51_ARGS=json.dumps({"paths": sorted(roots | singles)}))
    raw = run([os.path.join(HERE, "wp_eval.sh"), args.host, args.site, os.path.join(HERE, "file_hashes.php")], env=env)
    server = json.loads(raw)
    server_hashes = server["hashes"]

    changed, missing = [], []
    for p in deployable:
        blob = subprocess.run(["git", "show", "%s:%s" % (args.rev, p)], cwd=repo_dir, capture_output=True).stdout
        local = hashlib.md5(blob).hexdigest()
        remote = server_hashes.get(p)
        if remote is None:
            missing.append(p)
        elif remote != local and not remote.startswith("size:"):
            changed.append(p)
    deployable_set = set(deployable)
    server_only = sorted(p for p in server_hashes if p not in deployable_set and not ignored(p, patterns)
                         and any(p.startswith(r + "/") for r in roots))

    out = {
        "repo": args.repo or repo_dir, "rev": args.rev, "site": args.site, "compared_roots": sorted(roots),
        "tracked_files_compared": len(deployable),
        "changed_on_server": changed[:200], "missing_on_server": missing[:200], "server_only": server_only[:200],
        "notes": server.get("notes", []),
        "state": "clean" if not (changed or missing or server_only) else "drifted",
        "caveat": "Built assets that the deploy generates, or files excluded by DeployHQ rules outside .deployignore, "
                  "show up as server-only or missing. Read the lists before calling it drift.",
    }
    json.dump(out, sys.stdout, indent=2)
    print()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("revision")
    r.add_argument("--repo", required=True)
    r.add_argument("--branch", required=True)
    r.add_argument("--deployed-rev", required=True)
    d = sub.add_parser("drift")
    d.add_argument("--repo")
    d.add_argument("--repo-dir")
    d.add_argument("--rev", required=True)
    d.add_argument("--host", required=True, choices=["pressable", "wpcom"])
    d.add_argument("--site", required=True)
    args = ap.parse_args()
    if args.cmd == "revision":
        revision(args)
    else:
        if not (args.repo or args.repo_dir):
            ap.error("drift needs --repo or --repo-dir")
        drift(args)


if __name__ == "__main__":
    main()
