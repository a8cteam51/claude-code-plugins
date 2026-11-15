"""Render the audit and the runbook as one self-contained HTML page (REPORT.html).

Called by build_audit.py with what it already computed. No external assets: the page
opens from disk and can be attached or shared as one file.

The page is written for the person deciding whether, and when, to take this
migration on: what kind of job it is, what takes calendar time, who else is
needed, and the whole runbook as it stands. Values that only exist once the new
site is created (its address, its blog ID) show as highlighted placeholders.
"""
import html
import re

SEVERITY = [
    ("blocker", "Blockers", "Must be resolved before this site is scheduled."),
    ("decision", "Needs an answer", "Specific to this site. Someone has to choose before work starts."),
    ("manual", "Work beyond the standard migration", "A person does these during the migration."),
    ("auto", "Handled by the process", "An agent or script does these."),
    ("info", "Worth knowing", "No action on its own."),
]
ACTOR = {"agent": ("Agent", "a-agent"), "human": ("Person", "a-human"), "both": ("Agent + person", "a-both")}

# Steps that cannot be finished in one sitting, and why.
WAITS = {
    "rehearse.ttl": "Lower DNS TTLs at least a day before the window.",
    "prep.woopayments": "The WooPayments team needs notice to re-link the account.",
    "prep.videopress": "The VideoPress move is arranged with the VideoPress team.",
    "prep.dns-access": "Registrar or DNS access may need the partner.",
    "verify.jetpack": "Jetpack's content checksum can take hours to report.",
    "post.subscribers": "Subscriber migration finishes by email, later.",
    "post.stragglers": "Checked again a day after cutover.",
    "decom.managed": "Team 51 monitoring picks the site up overnight.",
    "decom.wait": "The old site is kept, frozen, for at least a week.",
    "dns.zone-move": "The name server change is a separate, later step.",
    "staging.create": "The staging site comes last, after all DNS changes.",
}
# Tools and access each step needs. Shown as one list so nobody discovers a missing login mid-window.
NEEDS = {
    "sync.first": "Migration Assistant (MC)", "sync.source-exporter": "Migration Assistant (MC)",
    "sync.cleanup": "Blog RC (MC)", "verify.jetpack": "Jetpack debug tool", "post.jetpack-resync": "Jetpack debug tool",
    "post.stats": "Blog Stats Merger (MC)", "post.subscribers": "Jetpack tools (MC)", "post.videopress": "VideoPress tools (MC)",
    "cut.dns": "Registrar or DNS host login", "dns.zone-move": "Registrar or DNS host login",
    "rehearse.opsoasis": "OpsOasis settings", "decom.opsoasis": "OpsOasis settings",
    "prep.create-site": "team51 CLI with 1Password", "cut.freeze": "team51 CLI with 1Password",
    "verify.frontend": "Node 20+ and Google Chrome", "cut.frontend-baseline": "Node 20+ and Google Chrome",
    "prep.woopayments": "#woosupport (WooPayments team)", "prep.videopress": "#videopress",
}
WINDOW_PHASES = ("sync", "verify", "cut")

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1b;--muted:#6b6b66;--line:#e4e3de;--accent:#3858e9;--code:#f1f0ec;
--red:#c9372c;--red-bg:#fdecea;--amber:#9a6200;--amber-bg:#fff4dc;--blue:#2b5bb5;--blue-bg:#e8effc;--green:#2e7d4f;--green-bg:#e6f4ec;--grey-bg:#efefec;--ph:#7a3db8;--ph-bg:#f3ebfb}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#151514;--card:#1e1e1c;--ink:#ecebe7;--muted:#a3a29c;--line:#33322f;--accent:#8ea2ff;--code:#2a2926;
--red:#ff8a80;--red-bg:#3a1d1a;--amber:#ffcf70;--amber-bg:#3a2f14;--blue:#9cb8ff;--blue-bg:#1c2740;--green:#86d4a6;--green-bg:#17301f;--grey-bg:#2a2926;--ph:#cfa8ff;--ph-bg:#2f2240}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:24px 16px 80px}
header.top{padding:8px 0 20px;border-bottom:1px solid var(--line);margin-bottom:20px}
.eyebrow{color:var(--muted);font-size:13px;text-transform:uppercase;letter-spacing:.06em}
h1{font-size:28px;margin:4px 0 8px;line-height:1.2;word-break:break-word}
h2{font-size:20px;margin:36px 0 12px}
h3{font-size:16px;margin:20px 0 8px}
.meta{color:var(--muted);font-size:14px;display:flex;flex-wrap:wrap;gap:4px 16px}
nav.toc{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);margin:0 -16px 8px;padding:8px 16px;display:flex;gap:16px;overflow-x:auto;white-space:nowrap;font-size:14px}
nav.toc a{color:var(--muted);text-decoration:none}nav.toc a:hover{color:var(--accent)}
.verdict{display:inline-block;font-weight:600;border-radius:999px;padding:4px 12px;font-size:14px;margin-top:6px}
.v-hold{background:var(--red-bg);color:var(--red)}.v-decide{background:var(--amber-bg);color:var(--amber)}.v-ready{background:var(--green-bg);color:var(--green)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.card .n{font-size:26px;font-weight:650;line-height:1.1}.card .l{color:var(--muted);font-size:13px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:12px 0}
.callout{border-left:4px solid var(--accent);background:var(--card);border-radius:0 10px 10px 0;padding:12px 16px;margin:12px 0}
.callout.warn{border-color:var(--amber)}.callout.bad{border-color:var(--red)}
ul.clean{list-style:none;padding:0;margin:0}ul.clean li{padding:8px 0;border-bottom:1px solid var(--line)}ul.clean li:last-child{border-bottom:0}
.chip{display:inline-block;font-size:12px;font-weight:600;border-radius:6px;padding:1px 8px;margin-right:6px;vertical-align:1px;white-space:nowrap}
.s-blocker{background:var(--red-bg);color:var(--red)}.s-decision{background:var(--amber-bg);color:var(--amber)}.s-manual{background:var(--blue-bg);color:var(--blue)}
.s-auto{background:var(--green-bg);color:var(--green)}.s-info{background:var(--grey-bg);color:var(--muted)}
.a-agent{background:var(--green-bg);color:var(--green)}.a-human{background:var(--blue-bg);color:var(--blue)}.a-both{background:var(--amber-bg);color:var(--amber)}
.who{color:var(--muted);font-size:13px}
details{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:8px 0}
details>summary{cursor:pointer;padding:12px 16px;list-style:none;font-weight:550}
details>summary::-webkit-details-marker{display:none}
details>summary:before{content:"▸";display:inline-block;width:16px;color:var(--muted)}details[open]>summary:before{content:"▾"}
details .body{padding:0 16px 14px 32px;border-top:1px solid var(--line)}
.phase{margin-top:28px}.phase h3{display:flex;align-items:center;gap:8px}
.phase .count{color:var(--muted);font-weight:400;font-size:13px}
.window{border:2px dashed var(--accent);border-radius:14px;padding:4px 14px 10px;margin:20px -6px}
.window .tag{color:var(--accent);font-weight:600;font-size:13px;margin-top:8px}
.step .sid{color:var(--muted);font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.status{font-size:12px;font-weight:600;border-radius:6px;padding:1px 6px;margin-left:6px}
.st-done{background:var(--green-bg);color:var(--green)}.st-blocked{background:var(--red-bg);color:var(--red)}.st-skipped{background:var(--grey-bg);color:var(--muted)}
.verify{background:var(--green-bg);border-radius:8px;padding:8px 12px;margin-top:10px}
.untested{background:var(--amber-bg);color:var(--amber);border-radius:8px;padding:6px 10px;font-size:13px}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;background:var(--code);border-radius:4px;padding:1px 4px;word-break:break-word}
pre{background:var(--code);border-radius:8px;padding:10px 12px;overflow-x:auto;font-size:12.5px;line-height:1.45}pre code{background:none;padding:0;word-break:normal;white-space:pre}
.ph{background:var(--ph-bg);color:var(--ph);border-radius:4px;padding:0 3px;font-weight:600}
table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0;display:block;overflow-x:auto}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{color:var(--muted);font-weight:600}
a{color:var(--accent)}
.legend{color:var(--muted);font-size:13px;margin:6px 0 0}
footer{color:var(--muted);font-size:13px;margin-top:48px;border-top:1px solid var(--line);padding-top:12px}
@media print{nav.toc{display:none}details{break-inside:avoid}details:not([open])>.body{display:block}body{background:#fff}}
"""


def esc(text):
    return html.escape(str(text), quote=True)


def inline(text):
    """Escape, then apply inline markdown: code, bold, italics, links, placeholders."""
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append("<code>%s</code>" % placeholders(esc(p[1:-1])))
            continue
        e = esc(p)
        e = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', e)
        # A URL stops at a placeholder (escaped "<"), so the placeholder is highlighted, not linked.
        e = re.sub(r'(?<!href=")(?<![">])(https?://(?:(?!&lt;)[^\s<)])*(?:(?!&lt;)[^\s<).,;:]))', r'<a href="\1">\1</a>', e)
        e = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", e)
        e = re.sub(r"(?<![*\w])\*([^*\n]+?)\*(?![*\w])", r"<em>\1</em>", e)
        out.append(placeholders(e))
    return "".join(out)


def placeholders(escaped):
    return re.sub(r"&lt;([a-z0-9][a-z0-9 /._-]*)&gt;", r'<span class="ph" title="Filled in once known">&lt;\1&gt;</span>', escaped)


def md(text):
    """Small markdown renderer for the runbook and finding text: paragraphs, lists, code, tables, quotes."""
    lines = (text or "").strip("\n").split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>%s</code></pre>" % placeholders(esc("\n".join(code))))
            continue
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s|:-]+\|$", lines[i + 1].strip()):
            head = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (
                "".join("<th>%s</th>" % inline(c) for c in head),
                "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in rows)))
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            ordered = m.group(2)[0].isdigit()
            items = []
            while i < len(lines):
                m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if m:
                    items.append([len(m.group(1)), m.group(3)])
                elif lines[i].strip() and items and lines[i].startswith("  "):
                    items[-1][1] += "\n" + lines[i].strip()
                else:
                    break
                i += 1
            tag = "ol" if ordered else "ul"
            out.append("<%s>%s</%s>" % (tag, "".join(
                '<li%s>%s</li>' % (' style="margin-left:%dpx"' % (ind * 6) if ind else "", inline(t).replace("\n", "<br>")) for ind, t in items), tag))
            continue
        if line.startswith("> "):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i][1:].strip())
                i += 1
            joined = " ".join(block)
            cls = "untested" if joined.startswith("UNTESTED") else "callout"
            out.append('<div class="%s">%s</div>' % (cls, inline(joined)))
            continue
        if not line.strip():
            i += 1
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith("```") and not re.match(r"^(\s*)([-*]|\d+\.)\s", lines[i]) \
                and not lines[i].startswith("> ") and not (lines[i].startswith("|") and i + 1 < len(lines) and lines[i + 1].strip().startswith("|-")):
            para.append(lines[i].strip())
            i += 1
        out.append("<p>%s</p>" % inline(" ".join(para)))
    return "\n".join(out)


def render(domain, meta, verdict, counts, findings, steps, values, state, standing_rules, missing_inputs, phases):
    v_cls = {"HOLD": "v-hold", "READY AFTER DECISIONS": "v-decide"}.get(verdict, "v-ready")
    phase_name = dict(phases)
    h = []
    h.append("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>")
    h.append("<title>Migration plan: %s</title><style>%s</style></head><body><div class='wrap'>" % (esc(domain), CSS))

    # ---- header
    h.append("<header class='top'><div class='eyebrow'>Pressable → WordPress.com migration</div><h1>%s</h1>" % esc(domain))
    h.append("<div class='meta'>%s</div>" % "".join("<span>%s</span>" % inline(m) for m in meta))
    shown = {"HOLD": "On hold", "READY AFTER DECISIONS": "Ready after decisions", "READY TO PLAN": "Ready to plan"}.get(verdict, verdict)
    h.append("<div class='verdict %s'>%s</div></header>" % (v_cls, esc(shown)))
    h.append("<nav class='toc'><a href='#overview'>Overview</a><a href='#involves'>What's involved</a><a href='#answers'>Needs an answer</a>"
             "<a href='#findings'>All findings</a><a href='#runbook'>Runbook</a></nav>")

    asks = [f for f in findings if f["severity"] in ("blocker", "decision")]
    manual = [f for f in findings if f["severity"] == "manual"]
    agent_steps = sum(1 for s in steps if s["actor"] == "agent")
    person_steps = len(steps) - agent_steps
    window_steps = [s for s in steps if s["phase"] in WINDOW_PHASES]

    # ---- overview
    h.append("<section id='overview'><h2>Overview</h2>")
    if counts["blocker"]:
        h.append("<div class='callout bad'><strong>Not ready to schedule.</strong> %d thing%s must be resolved first; they are listed under <a href='#answers'>Needs an answer</a>.</div>" % (counts["blocker"], "" if counts["blocker"] == 1 else "s"))
    elif counts["decision"]:
        h.append("<div class='callout warn'><strong>Ready once %d question%s answered.</strong></div>" % (counts["decision"], " is" if counts["decision"] == 1 else "s are"))
    else:
        h.append("<div class='callout'><strong>Ready to plan.</strong> Nothing needs deciding first.</div>")
    if missing_inputs:
        h.append("<div class='callout warn'><strong>Not checked:</strong> %s. Findings in these areas may be incomplete.</div>" % esc("; ".join(missing_inputs)))
    h.append("<div class='cards'>")
    for n, label in ((counts["blocker"], "blockers"), (counts["decision"], "need an answer"), (counts["manual"], "extra manual tasks"),
                     (len(steps), "runbook steps"), (len(window_steps), "steps in the cutover window")):
        h.append("<div class='card'><div class='n'>%d</div><div class='l'>%s</div></div>" % (n, label))
    h.append("</div></section>")

    # ---- what's involved
    h.append("<section id='involves'><h2>What's involved</h2>")
    h.append("<p>The shape of the job, to help decide whether to take it on now. Steps marked <span class='chip a-agent'>Agent</span> "
             "can be run by Claude; <span class='chip a-human'>Person</span> steps need you or someone else.</p>")
    h.append("<div class='panel'><h3 style='margin-top:0'>The cutover window</h3><p>One sitting, with the live site frozen: "
             "%d steps, from the go/no-go to the DNS change. The copy runs once and cannot be repeated, so the window has to be "
             "seen through or abandoned (abandoning means unfreezing the live site; nothing on it has changed). Choose quiet "
             "hours, and a time when you can stay with it.</p><ol>%s</ol></div>" % (
                 len(window_steps), "".join("<li>%s <span class='chip %s'>%s</span></li>" % (
                     inline(s["title"]), ACTOR[s["actor"]][1], ACTOR[s["actor"]][0]) for s in window_steps)))
    waits = [(s, WAITS[s["id"]]) for s in steps if s["id"] in WAITS]
    if waits:
        h.append("<div class='panel'><h3 style='margin-top:0'>Things that take calendar time</h3><ul class='clean'>%s</ul></div>" % "".join(
            "<li>%s <span class='who'>· %s</span></li>" % (esc(w), esc(phase_name[s["phase"]])) for s, w in waits))
    needs = []
    for s in steps:
        n = NEEDS.get(s["id"])
        if n and n not in needs:
            needs.append(n)
    if needs:
        h.append("<div class='panel'><h3 style='margin-top:0'>Access and tools you will need</h3><ul class='clean'>%s</ul></div>" % "".join(
            "<li>%s</li>" % esc(n) for n in needs))
    if manual:
        h.append("<div class='panel'><h3 style='margin-top:0'>What makes this site more than a standard migration</h3><ul class='clean'>%s</ul></div>" % "".join(
            "<li>%s<div class='who'>%s</div></li>" % (inline(f["title"]), esc(f["owner"])) for f in manual))
    h.append("<p class='legend'>%d steps for an agent, %d for a person or both.</p></section>" % (agent_steps, person_steps))

    # ---- needs an answer
    h.append("<section id='answers'><h2>Needs an answer</h2>")
    if asks:
        h.append("<ul class='clean panel'>")
        for f in asks:
            h.append("<li><span class='chip s-%s'>%s</span><strong>%s</strong><div class='who'>Who: %s</div><div>%s</div></li>" % (
                f["severity"], "Blocker" if f["severity"] == "blocker" else "Decision", inline(f["title"]), esc(f["owner"]), inline(f["action"])))
        h.append("</ul>")
    else:
        h.append("<p>Nothing.</p>")
    h.append("<details><summary>Already settled for every migration</summary><div class='body'><ul>%s</ul></div></details></section>" % "".join(
        "<li>%s</li>" % inline(r) for r in standing_rules))

    # ---- findings
    h.append("<section id='findings'><h2>All findings</h2><p>The evidence and the action for each item, for whoever does the work.</p>")
    for sev, heading, blurb in SEVERITY:
        group = [f for f in findings if f["severity"] == sev]
        if not group:
            continue
        h.append("<h3><span class='chip s-%s'>%d</span>%s</h3><p class='legend'>%s</p>" % (sev, len(group), esc(heading), esc(blurb)))
        for f in group:
            body = ""
            if f.get("detail"):
                body += md(f["detail"])
            if f.get("action"):
                body += "<p><strong>Action:</strong> %s</p>" % inline(f["action"])
            body += "<p class='who'>%s · %s · <code>%s</code></p>" % (esc(f["area"]), esc(f["owner"]), esc(f["id"]))
            h.append("<details><summary>%s</summary><div class='body'>%s</div></details>" % (inline(f["title"]), body))
    h.append("</section>")

    # ---- runbook
    h.append("<section id='runbook'><h2>Runbook</h2>")
    if not values.get("target_known"):
        h.append("<p>The new site does not exist yet, so its address and blog ID show as <span class='ph'>&lt;placeholders&gt;</span>. "
                 "Rebuild after the site is created to fill them in.</p>")
    in_window = False
    phase = None
    for s in steps:
        if s["phase"] != phase:
            if phase is not None:
                h.append("</div>")
            if s["phase"] in WINDOW_PHASES and not in_window:
                h.append("<div class='window'><div class='tag'>Cutover window: one sitting, live site frozen</div>")
                in_window = True
            if s["phase"] not in WINDOW_PHASES and in_window:
                h.append("</div>")
                in_window = False
            phase = s["phase"]
            n = sum(1 for x in steps if x["phase"] == phase)
            h.append("<div class='phase'><h3>%s <span class='count'>%d step%s</span></h3>" % (esc(phase_name[phase]), n, "" if n == 1 else "s"))
        status = (state.get("steps", {}).get(s["id"]) or {}).get("status", "todo")
        badge = "" if status == "todo" else "<span class='status st-%s'>%s</span>" % (esc(status), esc(status))
        label, cls = ACTOR[s["actor"]]
        body = md(s["body"].format_map(values))
        verify = "<div class='verify'><strong>Verify:</strong> %s</div>" % md(s["verify"].format_map(values))
        h.append("<details class='step'><summary><span class='chip %s'>%s</span>%s%s <span class='sid'>%s</span></summary><div class='body'>%s%s</div></details>" % (
            cls, label, inline(s["title"]), badge, esc(s["id"]), body, verify))
    if phase is not None:
        h.append("</div>")
    if in_window:
        h.append("</div>")
    h.append("</section>")
    h.append("<footer>Built by <code>build_audit.py</code> from the audit files. Re-run the audit shortly before cutover; sites change.</footer>")
    h.append("</div></body></html>")
    return "\n".join(h)
