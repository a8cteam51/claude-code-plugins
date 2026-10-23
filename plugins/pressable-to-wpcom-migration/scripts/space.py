#!/usr/bin/env python3
"""Shared migration status in the Team 51 Spacefast space.

    space.py check <domain> [--json] is there an entry for this site? exit 0 yes, 3 no
    space.py list                    every migration in the space
    space.py pull <domain> --dir DIR copy the site's state.json (progress, decisions, target) to DIR
    space.py publish --dir DIR [--event "text"] [--no-rebuild]
    space.py publish-process         publish pages/process.html as /process/

The space holds, per site, `migrations/<domain>/index.html` (the audit report and runbook, REPORT.html) and
`migrations/<domain>/status.json`, and `migrations/<domain>/state.json` so someone else can pick the migration
up with `pull`; at the root, `migrations.json` (one line per site) and `index.html` (built from
it). A publish sends only this site's files and the root pair, in additive mode, so other sites' pages
are never touched. Each publish is a Spacefast version, which is the revision history.

Needs `sf login` (the Spacefast CLI; `npx -y spacefast@0.5.0` is used when `sf` is not installed).
The space, team and live URL can be overridden with SPACEFAST_MIGRATIONS_SPACE, SPACEFAST_MIGRATIONS_TEAM
and SPACEFAST_MIGRATIONS_URL (for a test space).
Not `sites/`: the CLI takes a top-level `sites/` folder for build output and publishes only its contents.
Only summaries are published. Secrets never go in state.json, so they never reach the space.
"""
import argparse
import datetime
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runbook  # noqa: E402

SPACE = os.environ.get("SPACEFAST_MIGRATIONS_SPACE", "spc_6abbe00684ca4de091a9d91004daaec8")
TEAM = os.environ.get("SPACEFAST_MIGRATIONS_TEAM", "team-51")
SITE_URL = os.environ.get("SPACEFAST_MIGRATIONS_URL", "https://t51-pressable-migrations.space.fast").rstrip("/")
SF_VERSION = "0.5.0"
NOT_FOUND = 40  # sf fetch exit code for a 404
LOG_LIMIT = 50

PHASE_LABEL = dict(runbook.PHASES)
WINDOW = ("sync", "verify", "cut")
STATUS_LABEL = {
    "audited": "Audited", "hold": "On hold", "preparing": "Preparing", "cutover": "In cutover window",
    "live": "Live, after cutover", "blocked": "Blocked", "complete": "Complete",
}


class SpaceError(Exception):
    pass


def sf_cmd():
    return ["sf"] if shutil.which("sf") else ["npx", "-y", "spacefast@" + SF_VERSION]


def sf(args, check=True):
    p = subprocess.run(sf_cmd() + args + ["--json"], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    try:
        out = json.loads(p.stdout) if p.stdout.strip() else {}
    except ValueError:
        out = {}
    if check and p.returncode != 0:
        err = out.get("error") or {}
        hint = " Run `sf login`." if err.get("code") in ("auth_required", "unauthorized") else ""
        raise SpaceError("sf %s failed: %s%s" % (args[0], err.get("message") or p.stderr.strip()[-300:], hint))
    return p.returncode, out


def fetch_json(path):
    """The JSON file at `path` in the space, or None when it does not exist."""
    with tempfile.TemporaryDirectory() as tmp:
        dest = os.path.join(tmp, "out")
        code, out = sf(["fetch", path, "--space", SPACE, "--output", dest], check=False)
        if code == NOT_FOUND:
            return None
        if code != 0:
            err = (out.get("error") or {}).get("message", "exit %d" % code)
            raise SpaceError("could not read %s from the space: %s" % (path, err))
        with open(dest) as fh:
            return json.load(fh)


def whoami():
    _, out = sf(["whoami"])
    return ((out.get("data") or {}).get("account") or {}).get("name") or "unknown"


def bare(domain):
    return domain.lower().strip().split("://")[-1].rstrip("/")


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# --------------------------------------------------------------- status

def summarise(state):
    """Status fields derived from state.json."""
    meta = state.get("step_meta", {})
    order = state.get("step_order", [])
    steps = state.get("steps", {})

    def st(s):
        return steps.get(s, {}).get("status", "todo")

    phases = []
    for key, label in runbook.PHASES:
        ids = [s for s in order if meta.get(s, {}).get("phase") == key]
        if ids:
            phases.append({"key": key, "label": label, "total": len(ids),
                           "done": sum(st(s) in ("done", "skipped") for s in ids),
                           "blocked": sum(st(s) == "blocked" for s in ids)})
    todo = [s for s in order if st(s) == "todo"]
    blocked = [{"id": s, "title": meta.get(s, {}).get("title", s), "note": steps[s].get("note", "")}
               for s in order if st(s) == "blocked"]
    done_count = sum(st(s) in ("done", "skipped") for s in order)
    nxt = todo[0] if todo else None
    nxt_phase = meta.get(nxt, {}).get("phase") if nxt else None

    if not todo and not blocked:
        status = "complete"
    elif blocked:
        status = "blocked"
    elif done_count == 0:
        status = "hold" if state.get("verdict") == "HOLD" else "audited"
    elif nxt_phase in WINDOW:
        status = "cutover"
    elif nxt_phase in ("post", "dns", "staging", "decom"):
        status = "live"
    else:
        status = "preparing"

    recent = sorted(((v.get("at", ""), s, v) for s, v in steps.items() if v.get("status") != "todo" and v.get("at")), reverse=True)[:8]
    target = state.get("target") or {}
    return {
        "domain": state.get("domain"),
        "status": status,
        "status_label": STATUS_LABEL[status],
        "verdict": state.get("verdict"),
        "counts": state.get("counts", {}),
        "target": {"domain": target.get("domain"), "blog_id": target.get("blog_id")} if target.get("domain") else None,
        "progress": {"done": done_count, "total": len(order)},
        "current_phase": PHASE_LABEL.get(nxt_phase) if nxt_phase else None,
        "next_step": {"id": nxt, "title": meta.get(nxt, {}).get("title", nxt), "actor": meta.get(nxt, {}).get("actor")} if nxt else None,
        "blocked": blocked,
        "phases": phases,
        "recent": [{"at": at, "id": s, "title": meta.get(s, {}).get("title", s), "status": v["status"], "note": v.get("note", "")}
                   for at, s, v in recent],
        "decisions": {k: (v.get("value") if isinstance(v, dict) else v) for k, v in state.get("decisions", {}).items()},
        "audited": state.get("built"),
    }


def describe(entry):
    lines = ["%s: %s" % (entry["domain"], entry.get("status_label", entry.get("status")))]
    p = entry.get("progress") or {}
    if p.get("total"):
        lines.append("  progress: %d of %d steps%s" % (p["done"], p["total"], (" · " + entry["current_phase"]) if entry.get("current_phase") else ""))
    if entry.get("next_step"):
        lines.append("  next: %s (%s)" % (entry["next_step"]["title"], entry["next_step"]["id"]))
    for b in entry.get("blocked") or []:
        lines.append("  blocked: %s%s" % (b["title"], (" — " + b["note"]) if b.get("note") else ""))
    if entry.get("target"):
        lines.append("  target: %s (blog ID %s)" % (entry["target"]["domain"], entry["target"]["blog_id"]))
    lines.append("  started by %s on %s · last update %s by %s" % (
        entry.get("started_by", "?"), entry.get("started_at", "?"), entry.get("updated_at", "?"), entry.get("updated_by", "?")))
    lines.append("  page: %s/migrations/%s/" % (SITE_URL, entry["domain"]))
    return "\n".join(lines)


# --------------------------------------------------------------- pages

CSS = """
:root{--bg:#f7f8f8;--fg:#1b2023;--muted:#5c676d;--rule:#d9dfe1;--accent:#0e7c76;--card:#fff;
--ok:#1d7a3e;--warn:#9a6200;--bad:#b3261e;--live:#2f5fb3}
@media (prefers-color-scheme:dark){:root{--bg:#121618;--fg:#e4e9ea;--muted:#94a1a6;--rule:#2b3337;--accent:#4cc3ba;--card:#1a2023;
--ok:#5fc27e;--warn:#e0a640;--bad:#f07a70;--live:#7aa5f0}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:40px 16px 64px}
h1{font-size:1.6rem;margin:0 0 4px}
.sub{color:var(--muted);margin:0 0 32px}
h2{font-size:1rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:32px 0 12px}
a.card{display:block;padding:16px 18px;background:var(--card);border:1px solid var(--rule);border-radius:8px;color:inherit;text-decoration:none}
a.card:hover{border-color:var(--accent)}
a.card strong{color:var(--accent)}
.empty{color:var(--muted);padding:16px 18px;border:1px dashed var(--rule);border-radius:8px}
.table{overflow-x:auto;border:1px solid var(--rule);border-radius:8px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:.95rem}
th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--rule);vertical-align:top}
th{font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:0}
td a{color:var(--accent);font-weight:600;text-decoration:none}
.muted{color:var(--muted);font-size:.85rem}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.78rem;font-weight:600;border:1px solid currentColor;white-space:nowrap}
.s-complete{color:var(--ok)}.s-live{color:var(--live)}.s-cutover{color:var(--warn)}.s-blocked,.s-hold{color:var(--bad)}
.s-audited,.s-preparing{color:var(--muted)}
.bar{height:6px;background:var(--rule);border-radius:3px;overflow:hidden;margin-top:6px;min-width:80px}
.bar span{display:block;height:100%;background:var(--accent)}
"""


def page(title, body):
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'><title>%s</title><style>%s</style></head>"
            "<body><main>%s</main></body></html>\n") % (html.escape(title), CSS, body)


def render_index(sites):
    e = html.escape
    rows = []
    for s in sorted(sites, key=lambda x: x.get("updated_at", ""), reverse=True):
        p = s.get("progress") or {}
        pct = int(100 * p.get("done", 0) / p["total"]) if p.get("total") else 0
        nxt = s.get("next_step") or {}
        where = e(s.get("current_phase") or "") + ("<div class='muted'>Next: %s</div>" % e(nxt.get("title", "")) if nxt else "")
        if s.get("blocked"):
            where += "<div class='muted'>Blocked: %s</div>" % e(", ".join(b["title"] for b in s["blocked"]))
        rows.append("<tr><td><a href='migrations/%s/'>%s</a>%s</td><td><span class='badge s-%s'>%s</span></td><td>%s</td>"
                    "<td>%d of %d<div class='bar'><span style='width:%d%%'></span></div></td><td>%s<div class='muted'>%s</div></td></tr>" % (
                        e(s["domain"]), e(s["domain"]),
                        ("<div class='muted'>→ %s</div>" % e(s["target"]["domain"])) if s.get("target") else "",
                        e(s.get("status", "")), e(s.get("status_label", "")), where or "—",
                        p.get("done", 0), p.get("total", 0), pct, e(s.get("updated_by", "")), e(s.get("updated_at", ""))))
    table = ("<div class='table'><table><thead><tr><th>Site</th><th>Status</th><th>Where</th><th>Steps</th><th>Last update</th></tr></thead>"
             "<tbody>%s</tbody></table></div>" % "".join(rows)) if rows else "<div class='empty'>No migrations recorded here yet.</div>"
    body = ("<h1>Pressable → WordPress.com migrations</h1>"
            "<p class='sub'>Team 51. Process reference and the status of each site migration.</p>"
            "<h2>Process</h2><a class='card' href='process/'><strong>Migration process</strong><br>"
            "Every step, who does it, and the branches the audit decides.</a>"
            "<h2>Migrations</h2>%s"
            "<p class='muted' style='margin-top:24px'>Updated by the <code>pressable-to-wpcom-migration</code> plugin. "
            "Each site's page is its audit report and runbook as of its last update.</p>") % table
    return page("Pressable Migrations", body)


def site_page(d, entry):
    report = os.path.join(d, "REPORT.html")
    if os.path.exists(report):
        with open(report) as fh:
            return fh.read()
    return page("Migration: " + entry["domain"], "<h1>%s</h1><pre>%s</pre>" % (html.escape(entry["domain"]), html.escape(describe(entry))))


# --------------------------------------------------------------- commands

def cmd_check(domain, as_json=False):
    entry = fetch_json("/migrations/%s/status.json" % domain)
    if not entry:
        print("%s: no entry in the migrations space" % domain)
        return 3
    print(json.dumps(entry, indent=2) if as_json else describe(entry))
    return 0


def cmd_pull(domain, d):
    path = os.path.join(d, "state.json")
    if os.path.exists(path):
        print("%s already exists. Move it aside first if the space's copy should replace it." % path)
        return 1
    state = fetch_json("/migrations/%s/state.json" % domain)
    if not state:
        print("%s: no state in the migrations space" % domain)
        return 3
    os.makedirs(d, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")
    print("wrote %s (%d steps recorded). Re-run the audit into this folder to rebuild the report." % (
        path, sum(1 for v in state.get("steps", {}).values() if v.get("status") != "todo")))
    return 0


def cmd_list():
    sites = fetch_json("/migrations.json") or []
    if not sites:
        print("no migrations recorded")
    for s in sorted(sites, key=lambda x: x.get("updated_at", ""), reverse=True):
        nxt = (s.get("next_step") or {}).get("id") or ""
        print("%-36s %-20s %-10s %s" % (s["domain"], s.get("status_label", ""), "%d/%d" % ((s.get("progress") or {}).get("done", 0), (s.get("progress") or {}).get("total", 0)), nxt))
    return 0


def cmd_publish(d, event, rebuild):
    d = os.path.abspath(d)
    if rebuild:
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_audit.py"), "--dir", d],
                       check=True, stdout=subprocess.DEVNULL)
    with open(os.path.join(d, "state.json")) as fh:
        state = json.load(fh)
    domain = state.get("domain")
    if not domain:
        raise SpaceError("state.json has no domain. Run build_audit.py first.")
    who, stamp = whoami(), now()

    for attempt in (1, 2):
        remote = fetch_json("/migrations/%s/status.json" % domain) or {}
        entry = summarise(state)
        entry["started_by"] = remote.get("started_by") or who
        entry["started_at"] = remote.get("started_at") or stamp
        entry["updated_by"], entry["updated_at"] = who, stamp
        log = list(remote.get("log") or [])
        if attempt == 1:
            label = event or ("%s: %s" % (entry["status_label"], (entry.get("next_step") or {}).get("id") or "all steps closed"))
            log.append({"at": stamp, "by": who, "event": label})
        entry["log"] = log[-LOG_LIMIT:]
        brief = {k: entry[k] for k in ("domain", "status", "status_label", "progress", "current_phase", "next_step", "blocked",
                                       "target", "started_by", "updated_by", "updated_at")}
        sites = [s for s in (fetch_json("/migrations.json") or []) if s.get("domain") != domain] + [brief]

        with tempfile.TemporaryDirectory() as stage:
            os.makedirs(os.path.join(stage, "migrations", domain))
            files = {
                os.path.join("migrations", domain, "index.html"): site_page(d, entry),
                os.path.join("migrations", domain, "status.json"): json.dumps(entry, indent=2) + "\n",
                os.path.join("migrations", domain, "state.json"): json.dumps(state, indent=2) + "\n",
                "migrations.json": json.dumps(sites, indent=2) + "\n",
                "index.html": render_index(sites),
            }
            for rel, text in files.items():
                with open(os.path.join(stage, rel), "w") as fh:
                    fh.write(text)
            msg = "%s: %s (%s)" % (domain, event or entry["status_label"], who)
            _, out = sf(["publish", stage, "--space", SPACE, "--team", TEAM, "--publish-mode", "additive",
                         "-m", msg[:200], "--wait", "-y"])
        version = ((out.get("data") or {}).get("version") or {}).get("ref", "?")

        # Another publish in the same seconds can replace migrations.json without this site. Check, and redo once.
        check = fetch_json("/migrations.json") or []
        if any(s.get("domain") == domain and s.get("updated_at") == stamp for s in check):
            print("published %s (%s) as version %s" % (domain, entry["status_label"], version))
            print(describe(entry))
            return 0
        print("migrations.json was replaced by another publish; retrying", file=sys.stderr)
    raise SpaceError("this site is missing from migrations.json after two publishes. Its own page is up to date; publish again later.")


def cmd_publish_process():
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pages", "process.html")
    with tempfile.TemporaryDirectory() as stage:
        os.makedirs(os.path.join(stage, "process"))
        shutil.copy(src, os.path.join(stage, "process", "index.html"))
        _, out = sf(["publish", stage, "--space", SPACE, "--team", TEAM, "--publish-mode", "additive",
                     "-m", "Process page (%s)" % whoami(), "--wait", "-y"])
    print("published the process page as version %s: %s/process/" % (
        ((out.get("data") or {}).get("version") or {}).get("ref", "?"), SITE_URL))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check")
    c.add_argument("domain")
    c.add_argument("--json", action="store_true", help="the full status: decisions, recent steps, the log")
    sub.add_parser("list")
    sub.add_parser("publish-process")
    u = sub.add_parser("pull")
    u.add_argument("domain")
    u.add_argument("--dir", required=True)
    p = sub.add_parser("publish")
    p.add_argument("--dir", required=True)
    p.add_argument("--event", help="what happened, for the site's log and the version message")
    p.add_argument("--no-rebuild", action="store_true", help="publish REPORT.html as it is, without re-running build_audit.py")
    a = ap.parse_args()
    try:
        if a.command == "check":
            return cmd_check(bare(a.domain), a.json)
        if a.command == "list":
            return cmd_list()
        if a.command == "publish-process":
            return cmd_publish_process()
        if a.command == "pull":
            return cmd_pull(bare(a.domain), a.dir)
        return cmd_publish(a.dir, a.event, not a.no_rebuild)
    except SpaceError as exc:
        print("space: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
