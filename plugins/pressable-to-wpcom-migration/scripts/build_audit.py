#!/usr/bin/env python3
"""Build the audit report and runbook from the files in a migration folder.

    build_audit.py --dir migrations/example.com

Reads (all optional except site.json):
    site.json        output of site_audit.php on the source
    pressable.json   Pressable site details (pressable_get_site)
    related.json     list of related Pressable sites
    dns-*.json       output of dns_audit.py, one per apex domain
    deploy.json      deploy findings (see the audit skill for the shape)
    wpcom.json       WordPress.com-side facts: subscribers, views, plans, existing sites
    context.json     notes from P2, Slack and Linear
    state.json       decisions, target site and step progress (kept across rebuilds)

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
INPUTS = [("site.json", "Site inventory (WP-CLI)"), ("pressable.json", "Pressable site details"), ("related.json", "Related Pressable sites"),
          ("dns-*.json", "DNS and registrar"), ("deploy.json", "Deploy state"), ("wpcom.json", "WordPress.com-side facts (subscribers, stats, plans)"),
          ("context.json", "Context from P2, Slack and Linear")]


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as fh:
        text = fh.read().strip()
    if not text:
        return default
    return json.loads(text)


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

    decisions = {}
    for key, value in state["decisions"].items():  # "a.b" keys become nested for the checks.
        node = decisions
        parts = key.split(".", 1) if key.startswith("registrar_access.") else [key]
        if len(parts) == 2:
            node = decisions.setdefault(parts[0], {})
            node[parts[1]] = value.get("value") if isinstance(value, dict) else value
        else:
            decisions[key] = value.get("value") if isinstance(value, dict) else value

    manifest = {
        "site": site,
        "pressable": load(os.path.join(d, "pressable.json"), {}),
        "related": load(os.path.join(d, "related.json"), []),
        "dns": [load(p) for p in sorted(glob.glob(os.path.join(d, "dns-*.json"))) if load(p)],
        "deploy": load(os.path.join(d, "deploy.json")),
        "wpcom": load(os.path.join(d, "wpcom.json"), {}),
        "context": load(os.path.join(d, "context.json"), {}),
        "decisions": decisions,
        "target": state["target"],
    }
    missing_inputs = [label for pattern, label in INPUTS if not glob.glob(os.path.join(d, pattern))]

    findings = checks.run_all(manifest)
    switched_on = {s for f in findings for s in f.get("steps", [])}
    steps = runbook.build(manifest, switched_on)

    home = site["core"]["home"]
    domain = re.sub(r"^https?://", "", home).rstrip("/")
    apex = (manifest["dns"][0]["apex"] if manifest["dns"] else domain.replace("www.", "", 1))
    deploy_prod = (manifest.get("deploy") or {}).get("production") or {}
    target = state["target"]
    scripts = os.path.dirname(os.path.abspath(__file__))
    rel = os.path.relpath(d)
    shown_dir = rel if not rel.startswith("..") else d
    values = Safe(
        scripts=scripts, assets=os.path.join(os.path.dirname(scripts), "assets"), dir=shown_dir, domain=domain, apex=apex,
        pressable_id=manifest["pressable"].get("id") or domain,
        site_slug=re.sub(r"[^a-z0-9]+", "-", (manifest["pressable"].get("name") or apex.split(".")[0]).replace("-production", "")).strip("-"),
        source_blog_id=site.get("jetpack", {}).get("blog_id") or "<source-blog-id>",
        php_minor=".".join(site["core"]["php_version"].split(".")[:2]),
        repo=deploy_prod.get("repo") or "<a8cteam51/repo>",
        repo_name=(deploy_prod.get("repo") or "<repo>").split("/")[-1],
        deploy_branch=deploy_prod.get("branch") or "trunk",
    )
    if target.get("domain"):
        values["target"] = target["domain"]
    if target.get("blog_id"):
        values["target_blog_id"] = target["blog_id"]
    values["mc_assistant"] = ("https://mc.a8c.com/migration-assistant/?blog_id=%s" % target["blog_id"]) if target.get("blog_id") \
        else "https://mc.a8c.com/migration-assistant/ (add `?blog_id=<target blog ID>` once the target exists)"

    today = datetime.date.today().isoformat()
    counts = {sev: sum(1 for f in findings if f["severity"] == sev) for sev, _, _ in SEVERITY_HEADINGS}

    # ------------------------------------------------------------ REPORT.md
    r = []
    r.append("# Migration audit: %s\n" % domain)
    pr = manifest["pressable"]
    r.append("- **Audited:** %s · **Source:** Pressable site `%s` (%s) · **Blog ID:** %s" % (
        today, pr.get("id", "?"), pr.get("name", "?"), values["source_blog_id"]))
    r.append("- **WordPress** %s · **PHP** %s · **Theme** `%s` · **Plugins** %d active of %d" % (
        site["core"]["wp_version"], site["core"]["php_version"], site["themes"]["active"],
        sum(1 for p in site["plugins"] if p["active"]), len(site["plugins"])))
    r.append("- **Target:** %s" % (("`%s` (blog ID %s)" % (target.get("domain"), target.get("blog_id"))) if target.get("domain") else "not created yet"))
    verdict = "HOLD" if counts["blocker"] else ("READY AFTER DECISIONS" if counts["decision"] else "READY TO PLAN")
    r.append("- **Verdict:** %s — %d blockers, %d decisions, %d manual steps\n" % (verdict, counts["blocker"], counts["decision"], counts["manual"]))
    if missing_inputs:
        r.append("> **Not checked:** %s. Findings in these areas are incomplete.\n" % "; ".join(missing_inputs))

    def cell(text):
        return (text or "").replace("|", "/").replace("\n", " ").strip()

    def first_sentence(text):
        text = cell(text)
        m = re.match(r"(.+?[.!?])(\s|$)", text)
        return m.group(1) if m else text

    asks = [f for f in findings if f["severity"] in ("blocker", "decision")]
    r.append("## Summary\n")
    if counts["blocker"]:
        r.append("**This site should not be scheduled yet.** %d thing%s must be resolved first.\n" % (counts["blocker"], "" if counts["blocker"] == 1 else "s"))
    elif counts["decision"]:
        r.append("**This site can be migrated once %d question%s answered.**\n" % (counts["decision"], " is" if counts["decision"] == 1 else "s are"))
    else:
        r.append("**This site is ready to plan.** Nothing needs deciding first.\n")
    if asks:
        r.append("### Needs an answer\n")
        r.append("| | What | Who | What to do |\n|---|---|---|---|")
        for f in asks:
            r.append("| %s | %s | %s | %s |" % ("Blocker" if f["severity"] == "blocker" else "Decision", cell(f["title"]), cell(f["owner"]), first_sentence(f["action"])))
        r.append("")
    manual = [f for f in findings if f["severity"] == "manual"]
    if manual:
        r.append("### Work this site needs beyond the standard migration\n")
        r.append("| What | Who |\n|---|---|")
        for f in manual:
            r.append("| %s | %s |" % (cell(f["title"]), cell(f["owner"])))
        r.append("")
    r.append("### Already settled\n\nThese apply to every migration and are not questions for this site:\n")
    for rule in checks.STANDING_RULES:
        r.append("- " + rule)
    r.append("")
    r.append("---\n\n# Detail\n\nEverything below is the evidence and the action for each item above, for whoever does the work.\n")

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
    r.append("---\n\nBuilt by `build_audit.py` from the JSON files in this folder. Re-run the audit shortly before cutover; sites change.")
    with open(os.path.join(d, "REPORT.md"), "w") as fh:
        fh.write("\n".join(r) + "\n")

    # ----------------------------------------------------------- RUNBOOK.md
    b = []
    b.append("# Migration runbook: %s\n" % domain)
    b.append("Generated %s from the audit. Work top to bottom. Mark progress with:\n" % today)
    b.append("```bash\npython3 %s/state.py --dir %s done <step-id> [\"note\"]\npython3 %s/state.py --dir %s status\n```\n" % (scripts, shown_dir, scripts, shown_dir))
    b.append("Key values: source `%s` (Pressable `%s`, blog ID `%s`) → target `%s` (blog ID `%s`).\n" % (
        domain, values["pressable_id"], values["source_blog_id"], values["target"], values["target_blog_id"]))
    b.append("Rules that hold throughout:\n")
    b.append("- Every sync replaces the target database. Database changes on the target go in `post-sync.sh`, never by hand.")
    b.append("- Never install SafetyNet on the target, and never use `wpcom:clone-site` to create it.")
    b.append("- Nothing on the live site changes before the freeze, apart from agreed plugin cleanup.")
    b.append("- Nobody onboards or clicks \"finish setup\" for WooPayments on the new site. An existing account is re-linked by the WooPayments team.")
    b.append("- Stop at any failed verification. Do not improvise around it.\n")
    actor_label = {"agent": "Agent", "human": "Person", "both": "Agent + person"}
    phase = None
    for step in steps:
        if step["phase"] != phase:
            phase = step["phase"]
            b.append("## %s\n" % dict(runbook.PHASES)[phase])
        status = (state["steps"].get(step["id"]) or {}).get("status", "todo")
        box = {"done": "[x]", "skipped": "[-]", "blocked": "[!]"}.get(status, "[ ]")
        b.append("### %s %s\n" % (box, step["title"]))
        b.append("`%s` · %s%s\n" % (step["id"], actor_label[step["actor"]], "" if status == "todo" else " · **" + status + "**"))
        b.append(step["body"].format_map(values) + "\n")
        b.append("**Verify:** " + step["verify"].format_map(values) + "\n")
    with open(os.path.join(d, "RUNBOOK.md"), "w") as fh:
        fh.write("\n".join(b) + "\n")

    for step in steps:
        state["steps"].setdefault(step["id"], {"status": "todo"})
    state["step_order"] = [s["id"] for s in steps]
    state["domain"] = domain
    state["built"] = today
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
