#!/usr/bin/env python3
"""Compare a folder of staged plugin directories against a repo's vendored plugins.

The branch decides what may be updated. A plugin counts as vendored only when
git tracks files for it on the checked-out branch - a directory left on disk by
a previous checkout of another branch is not a vendored plugin, and a staged zip
with no tracked counterpart is not an update.

Reads WordPress plugin headers on a best-effort basis, falls back through
readme.txt / composer.json / package.json / version constants when the header is
unusable, and reports one record per staged plugin so the caller can decide what
to do. It never writes to either tree.

Usage:
    plugin_inventory.py --staged DIR --repo-plugins DIR [--format json|text]
"""

import argparse
import json
import os
import re
import subprocess
import sys

JUNK_NAMES = {".DS_Store", "__MACOSX", ".git", ".svn", "Thumbs.db"}
HEADER_FIELDS = {
    "plugin name": "name",
    "version": "version",
    "plugin uri": "uri",
    "text domain": "text_domain",
    "requires at least": "requires_wp",
    "requires php": "requires_php",
}
# A version we are willing to act on: starts with a digit, no PHP/template noise.
SANE_VERSION = re.compile(r"^[0-9][0-9A-Za-z._+\-]*$")


def is_junk(name):
    return name in JUNK_NAMES or name.startswith("._")


def read_head(path, limit=16384):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read(limit)
    except OSError:
        return ""


def parse_headers(text):
    """Pull `Name: value` pairs out of the plugin's opening comment block."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    block = text
    start = text.find("/*")
    if start != -1:
        end = text.find("*/", start)
        block = text[start : end if end != -1 else len(text)]
    found = {}
    for line in block.split("\n")[:60]:
        line = line.strip().lstrip("*").strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key in HEADER_FIELDS:
            value = value.strip().rstrip("*/").strip()
            # Trailing inline comments and stray markup.
            value = re.sub(r"\s*(//|#|-->).*$", "", value).strip()
            if value and HEADER_FIELDS[key] not in found:
                found[HEADER_FIELDS[key]] = value
    return found


def find_main_file(plugin_dir, slug):
    """Top-level PHP file carrying a `Plugin Name:` header."""
    candidates = []
    try:
        entries = sorted(os.listdir(plugin_dir))
    except OSError:
        return None, []
    for entry in entries:
        if not entry.lower().endswith(".php") or is_junk(entry):
            continue
        path = os.path.join(plugin_dir, entry)
        if not os.path.isfile(path):
            continue
        if re.search(r"^\s*\*?\s*Plugin Name\s*:", read_head(path), re.I | re.M):
            candidates.append(path)
    if not candidates:
        return None, []
    preferred = os.path.join(plugin_dir, slug + ".php")
    for path in candidates:
        if path == preferred:
            return path, candidates
    return candidates[0], candidates


def version_from_readme(plugin_dir):
    for name in ("readme.txt", "README.txt", "readme.md", "README.md"):
        path = os.path.join(plugin_dir, name)
        if not os.path.isfile(path):
            continue
        match = re.search(r"^\s*Stable tag\s*:\s*(.+)$", read_head(path), re.I | re.M)
        if match:
            value = match.group(1).strip()
            if SANE_VERSION.match(value):
                return value, name + " (Stable tag)"
    return None, None


def version_from_json(plugin_dir):
    for name in ("composer.json", "package.json"):
        path = os.path.join(plugin_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                value = json.load(handle).get("version")
        except (OSError, ValueError):
            continue
        if isinstance(value, str) and SANE_VERSION.match(value.strip()):
            return value.strip(), name
    return None, None


def version_from_constant(main_file):
    """`define( 'FOO_VERSION', '1.2.3' )` or `const VERSION = '1.2.3';`."""
    if not main_file:
        return None, None
    text = read_head(main_file, 65536)
    patterns = (
        r"define\(\s*['\"][A-Z0-9_]*VERSION['\"]\s*,\s*['\"]([0-9][^'\"]*)['\"]",
        r"const\s+[A-Z0-9_]*VERSION\s*=\s*['\"]([0-9][^'\"]*)['\"]",
        r"\$[A-Za-z0-9_]*version[A-Za-z0-9_]*\s*=\s*['\"]([0-9][^'\"]*)['\"]",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match and SANE_VERSION.match(match.group(1)):
            return match.group(1), "version constant in " + os.path.basename(main_file)
    return None, None


def describe(plugin_dir):
    """Everything we can learn about one plugin directory."""
    slug = os.path.basename(plugin_dir.rstrip("/"))
    notes = []
    main_file, candidates = find_main_file(plugin_dir, slug)
    if len(candidates) > 1:
        notes.append(
            "several top-level PHP files carry a Plugin Name header: "
            + ", ".join(os.path.basename(c) for c in candidates)
            + " - used " + os.path.basename(main_file)
        )
    headers = parse_headers(read_head(main_file)) if main_file else {}
    if not main_file:
        any_php = any(
            name.lower().endswith(".php")
            for name in os.listdir(plugin_dir)
            if not is_junk(name)
        ) if os.path.isdir(plugin_dir) else False
        if any_php:
            notes.append("no top-level PHP file with a Plugin Name header")
        else:
            # Seen for real: a directory left behind on a branch that does not
            # actually carry the plugin, holding nothing but a stray .DS_Store.
            notes.append("directory holds no PHP files at all - is this plugin on this branch?")

    version = headers.get("version", "").strip()
    source = "header in " + os.path.basename(main_file) if main_file else None
    if version and not SANE_VERSION.match(version):
        notes.append("unusable Version header: " + repr(version))
        version, source = "", None
    elif not version and main_file:
        notes.append("no Version header")

    if not version:
        for getter in (
            lambda: version_from_constant(main_file),
            lambda: version_from_readme(plugin_dir),
            lambda: version_from_json(plugin_dir),
        ):
            value, origin = getter()
            if value:
                version, source = value, origin
                notes.append("version recovered from " + origin)
                break

    return {
        "slug": slug,
        "path": os.path.abspath(plugin_dir),
        "name": headers.get("name") or slug.replace("-", " ").title(),
        "name_from_header": bool(headers.get("name")),
        "version": version or None,
        "version_source": source,
        "text_domain": headers.get("text_domain"),
        "main_file": os.path.basename(main_file) if main_file else None,
        "notes": notes,
    }


# --- PHP-compatible version_compare -----------------------------------------

_ORDER = {"dev": 1, "alpha": 2, "a": 2, "beta": 3, "b": 3, "rc": 4, "#": 10, "pl": 11, "p": 11}


def _canonical(version):
    out = []
    previous = ""
    for char in version.strip():
        if not char.isalnum():
            out.append(".")
        elif previous and previous.isdigit() != char.isdigit() and previous.isalnum():
            out.append(".")
            out.append(char)
        else:
            out.append(char)
        previous = char
    return [part for part in "".join(out).split(".") if part]


def _rank(part):
    if part.isdigit():
        return _ORDER["#"]
    return _ORDER.get(part.lower(), 0)


def version_compare(left, right):
    """-1, 0 or 1, matching PHP's version_compare ordering."""
    a, b = _canonical(left), _canonical(right)
    for index in range(min(len(a), len(b))):
        pa, pb = a[index], b[index]
        ra, rb = _rank(pa), _rank(pb)
        if ra != rb:
            return -1 if ra < rb else 1
        if ra == _ORDER["#"]:
            ia, ib = int(pa), int(pb)
            if ia != ib:
                return -1 if ia < ib else 1
        elif pa.lower() != pb.lower():
            return -1 if pa.lower() < pb.lower() else 1
    if len(a) == len(b):
        return 0
    longer, sign = (a, 1) if len(a) > len(b) else (b, -1)
    extra = longer[min(len(a), len(b))]
    return sign if _rank(extra) >= _ORDER["#"] else -sign


def git_tracked_slugs(plugins_root):
    """Plugin slugs git tracks under plugins_root on the checked-out branch.

    Returns None when plugins_root is not inside a git working copy, which means
    "cannot tell" - callers then fall back to what is on disk.
    """
    try:
        top = subprocess.run(
            ["git", "-C", plugins_root, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=30,
        )
        if top.returncode != 0:
            return None
        listing = subprocess.run(
            ["git", "-C", plugins_root, "ls-files", "-z", "--", "."],
            capture_output=True, text=True, timeout=120,
        )
        if listing.returncode != 0:
            return None
    except (OSError, subprocess.SubprocessError):
        return None

    slugs = set()
    for path in listing.stdout.split("\0"):
        if not path:
            continue
        head = path.split("/", 1)[0]
        if head and head != path:  # a file directly in plugins/ is not a plugin
            slugs.add(head)
    return slugs


def list_plugin_dirs(root):
    if not os.path.isdir(root):
        return []
    return sorted(
        os.path.join(root, name)
        for name in os.listdir(root)
        if os.path.isdir(os.path.join(root, name)) and not is_junk(name)
    )


def relative_files(root):
    """Every tracked-looking file under root, relative, junk excluded."""
    collected = set()
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not is_junk(d)]
        for name in files:
            if is_junk(name):
                continue
            collected.add(os.path.relpath(os.path.join(current, name), root))
    return collected


def match_vendored(staged, vendored_by_slug, vendored_records):
    slug = staged["slug"]
    if slug in vendored_by_slug:
        return vendored_by_slug[slug], "slug"
    lowered = {key.lower(): key for key in vendored_by_slug}
    if slug.lower() in lowered:
        return vendored_by_slug[lowered[slug.lower()]], "slug (case-insensitive)"
    # A zip may unpack to `slug-1.2.3`; try the slug with a trailing version cut.
    trimmed = re.sub(r"[-_.]v?\d[\d.]*$", "", slug)
    if trimmed and trimmed in vendored_by_slug:
        return vendored_by_slug[trimmed], "slug with version suffix removed"
    for record in vendored_records:
        if staged["name_from_header"] and record["name_from_header"]:
            if record["name"].strip().lower() == staged["name"].strip().lower():
                return record, "Plugin Name header"
    for record in vendored_records:
        if staged["text_domain"] and record["text_domain"] == staged["text_domain"]:
            return record, "Text Domain header"
    return None, None


def build(staged_root, repo_plugins_root):
    tracked = git_tracked_slugs(repo_plugins_root)
    on_disk = list_plugin_dirs(repo_plugins_root)
    if tracked is None:
        vendored_paths, untracked_on_disk = on_disk, set()
    else:
        vendored_paths = [p for p in on_disk if os.path.basename(p) in tracked]
        untracked_on_disk = {
            os.path.basename(p) for p in on_disk if os.path.basename(p) not in tracked
        }

    vendored_records = [describe(path) for path in vendored_paths]
    vendored_by_slug = {record["slug"]: record for record in vendored_records}

    results = []
    for path in list_plugin_dirs(staged_root):
        staged = describe(path)
        vendored, how = match_vendored(staged, vendored_by_slug, vendored_records)
        notes = list(staged["notes"])
        entry = {
            "slug": staged["slug"],
            "name": staged["name"],
            "staged_path": staged["path"],
            "main_file": staged["main_file"],
            "new_version": staged["version"],
            "new_version_source": staged["version_source"],
            "vendored_slug": vendored["slug"] if vendored else None,
            "vendored_path": vendored["path"] if vendored else None,
            "matched_by": how,
            "old_version": vendored["version"] if vendored else None,
            "old_version_source": vendored["version_source"] if vendored else None,
            "local_only_files": [],
        }

        if vendored and vendored["notes"]:
            notes.extend("vendored copy: " + note for note in vendored["notes"])

        if vendored is None:
            entry["status"] = "not-on-branch"
            if staged["slug"] in untracked_on_disk:
                notes.append(
                    "a directory of this name is on disk but git tracks nothing in it on "
                    "this branch - it is a leftover from another branch, not a vendored plugin"
                )
            else:
                notes.append("git tracks no plugin of this name on this branch")
            notes.append("skip it: this workflow updates what the branch already carries, it does not add plugins")
        elif how != "slug":
            notes.append("matched the vendored copy by " + how + ", not by directory name")

        if vendored is not None:
            local_only = sorted(relative_files(vendored["path"]) - relative_files(staged["path"]))
            entry["local_only_files"] = local_only[:20]
            entry["local_only_file_count"] = len(local_only)
            if local_only:
                notes.append(
                    str(len(local_only))
                    + " file(s) exist in the vendored copy but not in the update - the copy would delete them"
                )

        if "status" not in entry:
            if not staged["version"] and not (vendored and vendored["version"]):
                entry["status"] = "unknown-both-versions"
            elif not staged["version"]:
                entry["status"] = "unknown-new-version"
            elif vendored and not vendored["version"]:
                entry["status"] = "unknown-old-version"
            else:
                comparison = version_compare(staged["version"], vendored["version"])
                entry["status"] = {1: "upgrade", 0: "same", -1: "downgrade"}[comparison]

        entry["notes"] = notes
        entry["needs_review"] = entry["status"] not in ("upgrade", "same") or bool(
            entry["local_only_files"]
        ) or any("unusable" in note or "recovered" in note for note in notes)
        results.append(entry)

    return {
        "staged_dir": os.path.abspath(staged_root),
        "repo_plugins_dir": os.path.abspath(repo_plugins_root),
        "branch": git_branch(repo_plugins_root),
        "vendored_source": "git" if tracked is not None else "filesystem (not a git working copy)",
        "vendored_count": len(vendored_records),
        "untracked_dirs_on_disk": sorted(untracked_on_disk),
        "plugins": results,
    }


def git_branch(path):
    try:
        result = subprocess.run(
            ["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def render_text(report):
    lines = [
        "Staged:   " + report["staged_dir"],
        "Vendored: " + report["repo_plugins_dir"] + " (" + str(report["vendored_count"])
        + " plugins tracked on branch " + (report["branch"] or "?") + ")",
    ]
    if report["untracked_dirs_on_disk"]:
        lines.append(
            "On disk but untracked here, ignored: "
            + ", ".join(report["untracked_dirs_on_disk"])
        )
    lines.append("")
    if not report["plugins"]:
        lines.append("No plugin directories found in the staged folder.")
    for entry in report["plugins"]:
        flag = "  " if not entry["needs_review"] else "! "
        lines.append(
            flag
            + entry["slug"].ljust(42)
            + (entry["old_version"] or "-").rjust(10)
            + " -> "
            + (entry["new_version"] or "-").ljust(10)
            + "  "
            + entry["status"]
        )
        for note in entry["notes"]:
            lines.append("      - " + note)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", required=True, help="folder of unpacked plugin directories")
    parser.add_argument("--repo-plugins", required=True, help="the repo's plugins/ directory")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args()

    for path, label in ((args.staged, "--staged"), (args.repo_plugins, "--repo-plugins")):
        if not os.path.isdir(path):
            sys.stderr.write(label + " is not a directory: " + path + "\n")
            return 2

    report = build(args.staged, args.repo_plugins)
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
