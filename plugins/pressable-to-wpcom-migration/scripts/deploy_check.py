#!/usr/bin/env python3
"""Is a site's existing deploy connected and current?

Revision check (GitHub only, no server access):
    deploy_check.py revision --repo a8cteam51/site --branch trunk --deployed-rev <sha>

Drift check (compares files on the server with the deployed revision):
    deploy_check.py drift --repo a8cteam51/site --rev <sha> --host pressable --site example.com
    deploy_check.py drift --repo-dir /path/to/clone --rev <sha> --host pressable --site example.com

Pressable deploy allowlist (does .deployignore carry the block, and what deploys without it?):
    deploy_check.py allowlist --repo a8cteam51/site --rev trunk

All print JSON. All are read-only. A repo existing for a site proves nothing:
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
    """Repo tooling at the root (README, LICENSE, composer files, dotfiles).

    The drift and revision checks leave these out: a difference in them is not a
    deploy gap. Whether a deploy puts them on the server is not confirmed for
    WordPress.com, so `allowlist` lists them for plain exclusions instead.

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


ALLOWLIST_BEGIN = "# BEGIN Pressable deploy allowlist"
ALLOWLIST_END = "# END Pressable deploy allowlist"


def read_ignore(repo_dir, rev):
    try:
        return run(["git", "show", "%s:.deployignore" % rev], cwd=repo_dir)
    except RuntimeError:
        return ""


def patterns_of(text, host="pressable"):
    patterns = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    if host == "wpcom":
        # WordPress.com deployments apply .deployignore with rsync, which does not honour `!` lines.
        patterns = [p for p in patterns if not p.startswith("!")]
    return patterns


def without_allowlist(text):
    """The .deployignore text without the Pressable allowlist block, or None if it has none."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == ALLOWLIST_BEGIN), None)
    end = next((i for i, l in enumerate(lines) if l.strip() == ALLOWLIST_END and start is not None and i > start), None)
    if start is None or end is None:
        return None
    return "\n".join(lines[:start] + lines[end + 1:])


def _matches(pat, path, is_dir):
    if pat.endswith("/**"):
        return path.startswith(pat[:-3].lstrip("/") + "/")
    if pat.endswith("/"):
        if not is_dir:
            return False
        pat = pat.rstrip("/")
    if pat.startswith("**/"):
        pat = pat[3:]
    elif "/" in pat:
        want, have = pat.lstrip("/").split("/"), path.split("/")
        return len(want) == len(have) and all(fnmatch.fnmatchcase(h, w) for h, w in zip(have, want))
    return fnmatch.fnmatchcase(path.rsplit("/", 1)[-1], pat)


def ignored(path, patterns):
    """gitignore rules: the last matching pattern wins, and nothing inside an ignored directory comes back."""
    parts = path.split("/")
    for i in range(1, len(parts) + 1):
        sub, is_dir, verdict = "/".join(parts[:i]), i < len(parts), False
        for pat in patterns:
            neg = pat.startswith("!")
            if _matches(pat[1:] if neg else pat, sub, is_dir):
                verdict = not neg
        if verdict:
            return True
    return False


def with_repo(args, fn):
    tmp = None
    try:
        repo_dir = args.repo_dir
        if not repo_dir:
            tmp = tempfile.mkdtemp(prefix="t51-drift-")
            run(["gh", "repo", "clone", args.repo, tmp, "--", "--quiet", "--no-checkout"])
            repo_dir = tmp
        try:
            run(["git", "cat-file", "-e", args.rev + "^{commit}"], cwd=repo_dir)
        except RuntimeError:
            try:
                run(["git", "cat-file", "-e", "origin/%s^{commit}" % args.rev], cwd=repo_dir)
                args.rev = "origin/" + args.rev
            except RuntimeError:
                run(["git", "fetch", "--quiet", "origin", args.rev], cwd=repo_dir)
        fn(args, repo_dir)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def tracked_files(repo_dir, rev):
    return [p for p in run(["git", "ls-tree", "-r", "--name-only", rev], cwd=repo_dir).splitlines() if p]


def _allowlist(args, repo_dir):
    """Does .deployignore carry the Pressable deploy allowlist, and what would deploy without it?"""
    text = read_ignore(repo_dir, args.rev)
    rest = without_allowlist(text)
    out = {"repo": args.repo or repo_dir, "rev": args.rev, "present": rest is not None}
    if rest is not None:
        before, after = patterns_of(text), patterns_of(rest, "wpcom")
        # Tooling files are not set aside here: with the block gone, nothing confirms WordPress.com leaves a root
        # README or composer.json out (eagleman.com), so they are listed and get plain exclusions.
        tracked = tracked_files(repo_dir, args.rev)
        newly = [p for p in tracked if ignored(p, before) and not ignored(p, after)]
        tooling = sorted({"/" + p.split("/", 1)[0] + ("/" if "/" in p else "") for p in newly if is_tooling(p)})
        tops = {}
        for p in newly:
            parts = p.split("/")
            top = "/".join(parts[:2]) if parts[0] in ("themes", "plugins", "mu-plugins") and len(parts) > 2 else parts[0]
            tops[top] = tops.get(top, 0) + 1
        out.update(
            deployed_now=sum(1 for p in tracked if not ignored(p, before)),
            newly_deployed_without_block=sorted(tops.items()),
            newly_deployed_files=newly[:200],
            exclude_lines=tooling,
            note="Without the block, these paths deploy too. Exclude any that must not reach the server (tests, CI tooling, "
                 "other sites' themes) with plain lines in .deployignore; WordPress.com deployments ignore `!` lines. Add every "
                 "line in `exclude_lines` too: repo tooling at the root (README, LICENSE, composer files, dotfiles) would "
                 "otherwise land in wp-content, where plain files are publicly readable.")
    json.dump(out, sys.stdout, indent=2)
    print()


def _drift(args, repo_dir):
    patterns = patterns_of(read_ignore(repo_dir, args.rev), args.host)
    tracked = tracked_files(repo_dir, args.rev)
    deployable = [p for p in tracked if not ignored(p, patterns) and not is_tooling(p)]
    if not deployable:
        json.dump({"repo": args.repo or repo_dir, "rev": args.rev, "site": args.site, "tracked_files_compared": 0,
                   "state": "nothing-compared",
                   "evidence": ".deployignore excludes every tracked file for this host, so a deploy would copy nothing. "
                               "On WordPress.com that is the Pressable deploy allowlist; see `deploy_check.py allowlist`."},
                  sys.stdout, indent=2)
        print()
        return

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
    a = sub.add_parser("allowlist")
    a.add_argument("--repo")
    a.add_argument("--repo-dir")
    a.add_argument("--rev", required=True, help="branch or commit")
    args = ap.parse_args()
    if args.cmd == "revision":
        revision(args)
    else:
        if not (args.repo or args.repo_dir):
            ap.error("%s needs --repo or --repo-dir" % args.cmd)
        with_repo(args, _drift if args.cmd == "drift" else _allowlist)


if __name__ == "__main__":
    main()
