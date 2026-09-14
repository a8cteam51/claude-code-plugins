#!/usr/bin/env python3
"""Turn captured screenshots into a self-contained side-by-side HTML report.

Two things beyond plain image embedding earn their keep here:

1. Duplicate collapsing. Sites routinely serve the same page at several URLs
   (/shop/ and /products/, /cart/ and /checkout/ when empty). Showing those as
   separate rows makes the report look padded, so identical captures are merged
   into one row that lists every URL it covers.

2. Unchanged flagging. If before and after are byte-identical, that is usually
   a page the migration missed — worth surfacing rather than burying.

Output layout (all relative, so the folder can be zipped or moved):
  <dest>/comparison.html
  <dest>/full/<slug>-<viewport>-<side>.png   full-resolution
  <dest>/web/<slug>-<viewport>-<side>.jpg    downscaled, what the HTML loads

Usage:
  python3 build_report.py config.json --dest /path/to/output
"""
import argparse
import hashlib
import html
import json
import os
import shutil
import sys

from PIL import Image

# The progress and summary lines carry em dashes. Under a C/POSIX locale stdout
# defaults to ASCII, which would otherwise raise UnicodeEncodeError *after* every
# PNG has been copied and downscaled — the most expensive possible moment to die.
for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8", errors="replace")

Image.MAX_IMAGE_PIXELS = None
WEB_WIDTH = 900


# A run packs 100-200MB of PNGs and hashes each one twice — once to fingerprint
# duplicates, once to decide "unchanged". Cache so the second pass is free.
_md5_cache = {}


def md5(path):
    key = os.path.abspath(path)
    if key not in _md5_cache:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _md5_cache[key] = h.hexdigest()
    return _md5_cache[key]


def build(cfg, dest, include_full=True):
    out = cfg.get("out", "/tmp/shots")
    viewports = cfg.get("viewports") or [{"id": "desktop", "width": 1440, "height": 1000}]
    before_base = cfg["before"]["base"].rstrip("/")
    after_base = cfg["after"]["base"].rstrip("/")
    b_label = cfg["before"].get("label") or "Before"
    a_label = cfg["after"].get("label") or "After"
    b_sub = cfg["before"].get("sublabel") or ""
    a_sub = cfg["after"].get("sublabel") or ""

    for sub in (("full", "web") if include_full else ("web",)):
        os.makedirs(os.path.join(dest, sub), exist_ok=True)

    # Gather everything that actually got captured.
    rows, missing = [], []
    for pg in cfg["pages"]:
        entry = {"slug": pg["slug"], "title": pg["title"], "paths": [pg["path"]],
                 "before_path": pg.get("before_path", pg["path"]), "shots": {}}
        for vp in viewports:
            pair = {}
            for side in ("before", "after"):
                src = os.path.join(out, f"{pg['slug']}-{vp['id']}-{side}.png")
                if os.path.exists(src):
                    pair[side] = src
            if len(pair) == 2:
                entry["shots"][vp["id"]] = pair
            else:
                for side in ("before", "after"):
                    if side not in pair:
                        missing.append(f"{pg['slug']}/{vp['id']}/{side}")
        if entry["shots"]:
            rows.append(entry)

    # Collapse pages whose captures are identical on both sides and all viewports.
    fingerprints = {}
    for r in rows:
        r["_fp"] = tuple(sorted(
            (vid, md5(pair["before"]), md5(pair["after"]))
            for vid, pair in r["shots"].items()))
    merged = []
    for r in rows:
        twin = fingerprints.get(r["_fp"])
        if twin is not None:
            twin["paths"].extend(r["paths"])
            continue
        fingerprints[r["_fp"]] = r
        merged.append(r)
    collapsed = {r["slug"] for r in rows} - {r["slug"] for r in merged}
    rows = merged

    # Don't report a gap against a row that got collapsed into its twin — the
    # reader can't find it on the page. Pages that captured nothing at all never
    # entered `rows`, so they are untouched by this and still get reported.
    missing = [m for m in missing if m.split("/", 1)[0] not in collapsed]

    # Copy full-res, generate web-size, note which pages are visually unchanged.
    for r in rows:
        r["unchanged"] = True
        r["assets"] = {}
        for vid, pair in r["shots"].items():
            a = {}
            hashes = set()
            for side, src in pair.items():
                base = f"{r['slug']}-{vid}-{side}"
                if include_full:
                    shutil.copy2(src, os.path.join(dest, "full", base + ".png"))
                im = Image.open(src).convert("RGB")
                a[f"{side}_dims"] = im.size
                web = im.copy()
                web.thumbnail((WEB_WIDTH, 40000), Image.LANCZOS)
                web.save(os.path.join(dest, "web", base + ".jpg"),
                         quality=78, optimize=True, progressive=True)
                a[f"{side}_web"] = f"web/{base}.jpg"
                a[f"{side}_full"] = f"full/{base}.png" if include_full else ""
                hashes.add(md5(src))
            if len(hashes) > 1:
                r["unchanged"] = False
            r["assets"][vid] = a
        print(f"[report] packed {r['slug']}", flush=True)

    vp_ids = [v["id"] for v in viewports if any(v["id"] in r["assets"] for r in rows)]
    default_vp = vp_ids[0] if vp_ids else "desktop"

    nav = "\n".join(f'<a href="#{r["slug"]}">{html.escape(r["title"])}</a>' for r in rows)
    toggle = "".join(
        f'<button class="vp-btn{" on" if v == default_vp else ""}" data-vp="{v}">{v.title()}</button>'
        for v in vp_ids) if len(vp_ids) > 1 else ""

    def shot(a, side, alt):
        img = (f'<img loading="lazy" src="{html.escape(a[side + "_web"])}" '
               f'alt="{html.escape(alt)}">')
        full = a[side + "_full"]
        # Only link to the full-res file when it was actually written — a dead
        # click-through is worse than no click-through.
        if full:
            return (f'<div class="shot"><a href="{html.escape(full)}" target="_blank" '
                    f'rel="noopener">{img}</a></div>')
        return f'<div class="shot">{img}</div>'

    sections = []
    for r in rows:
        panels = []
        for vid in vp_ids:
            a = r["assets"].get(vid)
            if not a:
                continue
            bw, bh = a["before_dims"]
            aw, ah = a["after_dims"]
            narrow = " narrow" if max(bw, aw) <= 600 else ""
            panels.append(f"""
      <div class="pair{narrow}" data-vp="{vid}"{'' if vid == default_vp else ' hidden'}>
        <figure>
          <figcaption class="cap before">
            <span class="tag">{html.escape(b_label)}</span>
            {f'<span class="theme">{html.escape(b_sub)}</span>' if b_sub else ''}
            <a class="src" href="{html.escape(before_base + r['before_path'])}" target="_blank" rel="noopener">open ↗</a>
            <span class="dims">{bw}&times;{bh}</span>
          </figcaption>
          {shot(a, 'before', f"{b_label} — {r['title']}")}
        </figure>
        <figure>
          <figcaption class="cap after">
            <span class="tag">{html.escape(a_label)}</span>
            {f'<span class="theme">{html.escape(a_sub)}</span>' if a_sub else ''}
            <a class="src" href="{html.escape(after_base + r['paths'][0])}" target="_blank" rel="noopener">open ↗</a>
            <span class="dims">{aw}&times;{ah}</span>
          </figcaption>
          {shot(a, 'after', f"{a_label} — {r['title']}")}
        </figure>
      </div>""")

        paths_txt = " &middot; ".join(f"<code>{html.escape(p)}</code>" for p in r["paths"])
        badge = ('<span class="badge warn">identical before &amp; after</span>'
                 if r["unchanged"] else "")
        sections.append(f"""
<section class="cmp" id="{r['slug']}">
  <div class="cmp-head"><h2>{html.escape(r['title'])}</h2>{paths_txt}{badge}</div>
  {''.join(panels)}
</section>""")

    unchanged_n = sum(1 for r in rows if r["unchanged"])
    notes = []
    if unchanged_n:
        notes.append(f"{unchanged_n} page(s) rendered identically on both sites — "
                     "worth checking whether they were meant to change.")
    if missing:
        notes.append(f"{len(missing)} capture(s) missing: {html.escape(', '.join(missing[:8]))}"
                     + (" …" if len(missing) > 8 else ""))

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(cfg.get('project', 'Site Comparison'))} — Before / After</title>
<style>
  :root {{ --bg:#0f1115; --panel:#171a21; --line:#262b36; --text:#e9ecf1;
           --muted:#9aa3b2; --accent:#f26b21; --before:#6b7280; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
    font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Helvetica,Arial,sans-serif; }}
  header {{ padding:44px 32px 26px; border-bottom:1px solid var(--line); }}
  h1 {{ margin:0 0 8px; font-size:30px; letter-spacing:-.02em; }}
  .sub {{ color:var(--muted); max-width:780px; }}
  .sub b {{ color:var(--text); font-weight:600; }}
  .legend {{ display:flex; gap:26px; flex-wrap:wrap; margin-top:16px; font-size:13px; color:var(--muted); }}
  .legend span::before {{ content:""; display:inline-block; width:9px; height:9px;
    border-radius:50%; margin-right:7px; vertical-align:1px; }}
  .legend .b::before {{ background:var(--before); }}
  .legend .a::before {{ background:var(--accent); }}
  .notes {{ margin-top:14px; font-size:13px; color:var(--muted); }}
  .notes li {{ margin:3px 0; }}
  .bar {{ position:sticky; top:0; z-index:20; background:rgba(15,17,21,.94);
    backdrop-filter:blur(10px); border-bottom:1px solid var(--line);
    display:flex; align-items:center; gap:14px; padding:10px 32px; }}
  nav {{ display:flex; gap:7px; overflow-x:auto; white-space:nowrap; flex:1; }}
  nav a {{ color:var(--muted); text-decoration:none; font-size:12.5px;
    padding:5px 11px; border-radius:999px; border:1px solid var(--line); }}
  nav a:hover {{ color:var(--text); border-color:var(--accent); }}
  .vp {{ display:flex; gap:4px; flex-shrink:0; }}
  .vp-btn {{ background:transparent; color:var(--muted); border:1px solid var(--line);
    border-radius:999px; padding:5px 13px; font-size:12.5px; cursor:pointer; font-family:inherit; }}
  .vp-btn.on {{ background:var(--accent); border-color:var(--accent); color:#fff; }}
  main {{ padding:8px 32px 80px; }}
  .cmp {{ padding:38px 0 12px; border-bottom:1px solid var(--line); scroll-margin-top:64px; }}
  .cmp-head {{ display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; margin-bottom:16px; }}
  .cmp-head h2 {{ margin:0; font-size:20px; letter-spacing:-.01em; }}
  .cmp-head code {{ color:var(--muted); font-size:12.5px; }}
  .badge {{ font-size:11px; padding:3px 9px; border-radius:999px;
    border:1px solid #7a5c1e; background:#2a2110; color:#e5b567; }}
  .pair {{ display:grid; grid-template-columns:1fr 1fr; gap:22px; align-items:start; }}
  .pair[hidden] {{ display:none; }}
  /* A 390px capture stretched across half a 1440px screen is a blurry mess.
     Render phone shots near their native width instead. */
  .pair.narrow {{ grid-template-columns:repeat(2, minmax(0, 430px)); justify-content:center; }}
  figure {{ margin:0; background:var(--panel); border:1px solid var(--line);
    border-radius:12px; overflow:hidden; }}
  .cap {{ display:flex; align-items:center; gap:11px; padding:10px 14px;
    border-bottom:1px solid var(--line); font-size:12.5px; color:var(--muted); }}
  .tag {{ font-weight:700; letter-spacing:.06em; text-transform:uppercase; font-size:11px;
    padding:3px 9px; border-radius:999px; color:#fff; }}
  .before .tag {{ background:var(--before); }}
  .after .tag {{ background:var(--accent); }}
  .theme {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--text); }}
  .src {{ color:var(--muted); text-decoration:none; }}
  .src:hover {{ color:var(--accent); }}
  .dims {{ margin-left:auto; font-variant-numeric:tabular-nums; }}
  .shot {{ max-height:78vh; overflow-y:auto; overscroll-behavior:contain; }}
  .shot img {{ display:block; width:100%; height:auto; }}
  footer {{ padding:28px 32px 60px; color:var(--muted); font-size:13px; }}
  @media (max-width:1000px) {{ .pair {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(cfg.get('project', 'Site Comparison'))} — Before / After</h1>
  <p class="sub">Full-page captures{' at ' + ', '.join(f"{v['width']}px ({v['id']})" for v in viewports if v['id'] in vp_ids) if vp_ids else ''}.
  Each panel scrolls on its own — click any screenshot to open the full-resolution PNG.</p>
  <div class="legend">
    <span class="b">{html.escape(b_label)} — {html.escape(before_base.replace('https://', ''))}{(' · ' + html.escape(b_sub)) if b_sub else ''}</span>
    <span class="a">{html.escape(a_label)} — {html.escape(after_base.replace('https://', ''))}{(' · ' + html.escape(a_sub)) if a_sub else ''}</span>
  </div>
  {('<ul class="notes">' + ''.join(f'<li>{n}</li>' for n in notes) + '</ul>') if notes else ''}
</header>
<div class="bar">
  <nav>{nav}</nav>
  {f'<div class="vp">{toggle}</div>' if toggle else ''}
</div>
<main>
{''.join(sections)}
</main>
<footer>{len(rows)} page pair(s) &middot; {len(vp_ids)} viewport(s) &middot;
generated with headless Chromium, full-page, lazy content pre-scrolled and overlays suppressed.</footer>
<script>
document.querySelectorAll('.vp-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const vp = btn.dataset.vp;
    document.querySelectorAll('.vp-btn').forEach(b => b.classList.toggle('on', b === btn));
    document.querySelectorAll('.pair').forEach(p => {{ p.hidden = p.dataset.vp !== vp; }});
  }});
}});
</script>
</body>
</html>"""

    path = os.path.join(dest, "comparison.html")
    # Explicit utf-8: the document contains em dashes and ↗ glyphs, and the
    # process locale is not something to gamble a finished run on.
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"[report] wrote {path} — {len(rows)} rows, viewports: {', '.join(vp_ids)}")
    if notes:
        for n in notes:
            print("[report] note:", n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--dest", required=True)
    ap.add_argument("--no-full", action="store_true",
                    help="Skip the full-resolution PNGs (roughly 10x smaller output). "
                         "The click-through link is omitted rather than left dangling.")
    args = ap.parse_args()
    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    build(cfg, args.dest, include_full=not args.no_full)


main()
