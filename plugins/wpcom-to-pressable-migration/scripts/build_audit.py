#!/usr/bin/env python3
"""Build the audit report and runbook from the files in a migration folder.

    build_audit.py --dir migrations/example.com

Reads (all optional except site.json):
    site.json              output of site_audit.php on the WordPress.com source
    webroot.json           output of web_root.php on the source: what is served from outside wp-content
    wpcom.json             WordPress.com-side facts: blog ID, subscribers, stickers, other sites with the name
    activity.json          how often the live site is written to (see the audit skill for the shape)
    dns-*.json             output of dns_audit.py, one per apex domain
    deploy.json            repo, WordPress.com deployments, allowlist state
    pressable-related.json the partner's other Pressable sites
    context.json           notes from P2, Slack and Linear
    state.json             decisions, the Pressable target and step progress (kept across rebuilds)

Writes: manifest.json, findings.json, REPORT.md, RUNBOOK.md, and updates state.json.
Deterministic: the same inputs give the same report.
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checks  # noqa: E402
import runbook  # noqa: E402

SEVERITY_HEADINGS = [
    ("blocker", "Blockers", "Do not schedule this migration until each is resolved."),
    ("decision", "Needs an answer", "Specific to this site. Someone has to choose before work starts."),
    ("manual", "Manual steps", "A person does these during the migration."),
    ("auto", "Handled by the process", "An agent or script does these; listed so nothing is a surprise."),
    ("info", "Worth knowing", "No action on its own."),
]
INPUTS = [("site.json", "Site inventory (WP-CLI)"), ("webroot.json", "Files served from outside wp-content"),
          ("wpcom.json", "WordPress.com-side facts (subscribers, stickers, other sites)"), ("activity.json", "How often the site is written to"),
          ("dns-*.json", "DNS and registrar"), ("deploy.json", "Repo and deploys"), ("context.json", "Context from P2, Slack and Linear")]


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as fh:
        text = fh.read().strip()
    return json.loads(text) if text else default


class Safe(dict):
    def __missing__(self, key):
        return "<" + key.replace("_", "-") + ">"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    args = ap.parse_args()
    d = os.path.abspath(args.dir)
    site = load(os.path.join(d, "site.json"))
    if not site:
        sys.exit("site.json is missing or empty in %s. Run site_audit.php first." % d)

    state = load(os.path.join(d, "state.json"), {}) or {}
    state.setdefault("decisions", {})
    state.setdefault("steps", {})
    state.setdefault("target", {})
    decisions = {k: (v.get("value") if isinstance(v, dict) else v) for k, v in state["decisions"].items()}

    manifest = {
        "site": site,
        "webroot": load(os.path.join(d, "webroot.json")),
        "wpcom": load(os.path.join(d, "wpcom.json"), {}),
        "activity": load(os.path.join(d, "activity.json"), {}),
        "dns": [load(p) for p in sorted(glob.glob(os.path.join(d, "dns-*.json"))) if load(p)],
        "deploy": load(os.path.join(d, "deploy.json")),
        "pressable_related": load(os.path.join(d, "pressable-related.json"), []),
        "context": load(os.path.join(d, "context.json"), {}),
        "decisions": decisions,
        "target": state["target"],
    }
    missing_inputs = [label for pattern, label in INPUTS if not glob.glob(os.path.join(d, pattern))]

    findings = checks.run_all(manifest)
    switched_on = {s for f in findings for s in f.get("steps", [])}
    steps = runbook.build(manifest, switched_on)

    domain = re.sub(r"^https?://", "", site["core"]["home"]).rstrip("/")
    apex = manifest["dns"][0]["apex"] if manifest["dns"] else domain.replace("www.", "", 1)
    deploy = manifest.get("deploy") or {}
    target = state["target"]
    scripts = os.path.dirname(os.path.abspath(__file__))
    rel = os.path.relpath(d)
    shown_dir = rel if not rel.startswith("..") else d
    # Pressable site names take letters, digits and dashes; the CLI suggests the project name.
    site_name = decisions.get("pressable_site_name") or re.sub(r"[^a-z0-9]+", "-", apex.split(".")[0].lower()).strip("-")
    values = Safe(
        scripts=scripts, assets=os.path.join(os.path.dirname(scripts), "assets"), dir=shown_dir, domain=domain, apex=apex,
        site_name=site_name, work="/tmp/t51-reprint-" + site_name,
        source_blog_id=(manifest["wpcom"].get("blog_id") or site.get("jetpack", {}).get("blog_id") or "<source-blog-id>"),
        source_content_dir=site["core"].get("content_dir") or "/srv/htdocs/wp-content",
        source_prefix=site["core"].get("table_prefix") or "wp_",
        php_minor=".".join(site["core"]["php_version"].split(".")[:2]),
        repo=deploy.get("repo") or "<a8cteam51/repo>",
        repo_name=(deploy.get("repo") or "<repo>").split("/")[-1],
        branch=deploy.get("branch") or "trunk",
    )
    for key, name in (("domain", "target"), ("pressable_id", "pressable_id"), ("blog_id", "target_blog_id")):
        if target.get(key):
            values[name] = target[key]
    for key in ("partner_collaborator", "pressable_ips", "window_started"):
        if decisions.get(key):
            # state.py records each decision as {"value": ..., "at": ...}.
            v = decisions[key]
            values[key] = v.get("value") if isinstance(v, dict) else v

    today = datetime.date.today().isoformat()
    counts = {sev: sum(1 for f in findings if f["severity"] == sev) for sev, _, _ in SEVERITY_HEADINGS}
    verdict = "HOLD" if counts["blocker"] else ("READY AFTER DECISIONS" if counts["decision"] else "READY TO PLAN")

    def cell(text):
        return (text or "").replace("|", "/").replace("\n", " ").strip()

    def first_sentence(text):
        m = re.match(r"(.+?[.!?])(\s|$)", cell(text))
        return m.group(1) if m else cell(text)

    # ------------------------------------------------------------ REPORT.md
    r = ["# Migration audit: %s (WordPress.com → Pressable)\n" % domain]
    r.append("- **Audited:** %s · **Source:** WordPress.com blog %s · **Plan:** %s" % (
        today, values["source_blog_id"], ", ".join(s for s in manifest["wpcom"].get("stickers", []) if s.endswith(("-plan", "-bundle"))) or "unknown"))
    r.append("- **WordPress** %s · **PHP** %s · **Theme** `%s` · **Plugins** %d active of %d" % (
        site["core"]["wp_version"], site["core"]["php_version"], site["themes"]["active"],
        sum(1 for p in site["plugins"] if p["active"]), len(site["plugins"])))
    r.append("- **Target:** %s" % (("Pressable site %s (`%s`)" % (target.get("pressable_id"), target.get("domain"))) if target.get("pressable_id") else "not created yet"))
    r.append("- **Verdict:** %s — %d blockers, %d decisions, %d manual steps\n" % (verdict, counts["blocker"], counts["decision"], counts["manual"]))
    if missing_inputs:
        r.append("> **Not checked:** %s. Findings in these areas are incomplete.\n" % "; ".join(missing_inputs))
    r.append("## Summary\n")
    if counts["blocker"]:
        r.append("**This site should not be scheduled yet.** %d thing%s must be resolved first.\n" % (counts["blocker"], "" if counts["blocker"] == 1 else "s"))
    elif counts["decision"]:
        r.append("**This site can be migrated once %d question%s answered.**\n" % (counts["decision"], " is" if counts["decision"] == 1 else "s are"))
    else:
        r.append("**This site is ready to plan.** Nothing needs deciding first.\n")
    asks = [f for f in findings if f["severity"] in ("blocker", "decision")]
    if asks:
        r.append("### Needs an answer\n\n| | What | Who | What to do |\n|---|---|---|---|")
        for f in asks:
            r.append("| %s | %s | %s | %s |" % ("Blocker" if f["severity"] == "blocker" else "Decision", cell(f["title"]), cell(f["owner"]), first_sentence(f["action"])))
        r.append("")
    manual = [f for f in findings if f["severity"] == "manual"]
    if manual:
        r.append("### Work this site needs\n\n| What | Who |\n|---|---|")
        for f in manual:
            r.append("| %s | %s |" % (cell(f["title"]), cell(f["owner"])))
        r.append("")
    r.append("### Already settled\n")
    r.extend("- " + rule for rule in checks.STANDING_RULES)
    r.append("\n---\n\n# Detail\n")
    for sev, heading, blurb in SEVERITY_HEADINGS:
        group = [f for f in findings if f["severity"] == sev]
        if not group:
            continue
        r.append("## %s (%d)\n\n%s\n" % (heading, len(group), blurb))
        area = None
        for f in group:
            if f["area"] != area:
                area = f["area"]
                r.append("### %s\n" % area)
            r.append("**%s**" % f["title"])
            if f["detail"]:
                r.append("\n" + f["detail"].strip())
            if f["action"]:
                r.append("\n*Action:* " + f["action"].strip())
            r.append("\n*Who:* %s · `%s`\n" % (f["owner"], f["id"]))
    r.append("---\n\nBuilt by `build_audit.py` from the JSON files in this folder. Re-run the audit shortly before cutover.")
    with open(os.path.join(d, "REPORT.md"), "w") as fh:
        fh.write("\n".join(r) + "\n")

    # ----------------------------------------------------------- RUNBOOK.md
    b = ["# Migration runbook: %s (WordPress.com → Pressable)\n" % domain]
    b.append("Generated %s from the audit. Work top to bottom. Mark progress with:\n" % today)
    b.append("```bash\npython3 %s/state.py --dir %s done <step-id> [\"note\"]\npython3 %s/state.py --dir %s status\n```\n" % (scripts, shown_dir, scripts, shown_dir))
    b.append("Key values: source `%s` (blog `%s`) → Pressable `%s` (`%s`), Reprint work directory `%s`.\n" % (
        domain, values["source_blog_id"], values["pressable_id"], values["target"], values["work"]))
    b.append("Rules that hold throughout:\n")
    b.append("- The pull can be run again. The rehearsal proves it; the final pull in the window repeats it with the same work directory.")
    b.append("- The quarantine stays on the Pressable site from before the first pull until `cut.jetpack`. It keeps the copied Jetpack connection offline.")
    b.append("- The database diff (`window.verify`) is the go-live gate. With gaps unexplained, lift any freeze and stop.")
    b.append("- Pressable's GitHub integration is connected only after the allowlist is merged, and only just before DNS. Never DeployHQ.")
    b.append("- Only the apex and `www` records change. Mail and every other record stay as they are.")
    b.append("- Nothing on the live WordPress.com site changes without a yes: the Reprint plugin, the token and the freeze are all writes.")
    b.append("- Stop at any failed verification. Do not improvise around it.\n")
    actor_label = {"agent": "Agent", "human": "Person", "both": "Agent + person"}
    phase = None
    for step in steps:
        if step["phase"] != phase:
            phase = step["phase"]
            b.append("## %s\n" % dict(runbook.PHASES)[phase])
        status = (state["steps"].get(step["id"]) or {}).get("status", "todo")
        box = {"done": "[x]", "skipped": "[-]", "blocked": "[!]"}.get(status, "[ ]")
        b.append("### %s %s\n" % (box, step["title"].format_map(values)))
        b.append("`%s` · %s%s\n" % (step["id"], actor_label[step["actor"]], "" if status == "todo" else " · **" + status + "**"))
        b.append(step["body"].format_map(values) + "\n")
        b.append("**Verify:** " + step["verify"].format_map(values) + "\n")
    with open(os.path.join(d, "RUNBOOK.md"), "w") as fh:
        fh.write("\n".join(b) + "\n")

    for step in steps:
        state["steps"].setdefault(step["id"], {"status": "todo"})
    state["step_order"] = [s["id"] for s in steps]
    state["step_meta"] = {s["id"]: {"title": s["title"].format_map(values), "phase": s["phase"], "actor": s["actor"]} for s in steps}
    state.update(verdict=verdict, counts=counts, domain=domain, built=today, direction="wpcom-to-pressable")
    for name, payload in (("manifest.json", manifest), ("findings.json", findings), ("state.json", state)):
        with open(os.path.join(d, name), "w") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")

    print("%s: %s" % (domain, verdict))
    print("  %d blockers, %d decisions, %d manual, %d handled, %d info" % tuple(counts[s] for s, _, _ in SEVERITY_HEADINGS))
    print("  %d runbook steps" % len(steps))
    if missing_inputs:
        print("  not checked: " + "; ".join(missing_inputs))
    print("  %s\n  %s" % (os.path.join(d, "REPORT.md"), os.path.join(d, "RUNBOOK.md")))


if __name__ == "__main__":
    main()
