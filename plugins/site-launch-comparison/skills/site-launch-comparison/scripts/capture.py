#!/usr/bin/env python3
"""Capture full-page screenshots of two sites for a before/after comparison.

Designed to be run REPEATEDLY. Every run picks up where the last one stopped
and exits before its time budget expires. That matters because agent shells are
often capped at a few minutes per call and background processes don't survive
between calls — so a single long-running job would get killed halfway with
nothing to show. Resumability turns a fragile 20-minute job into a series of
cheap, safe ones.

Run it in a loop until it prints "REMAINING 0".

Usage:
  python3 capture.py config.json            # BUDGET env var controls seconds, default 110
"""
import json
import os
import signal
import sys
import time
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

# Seconds of capture work per run. Agent shells often cap a single call at a
# couple of minutes, so the default leaves headroom. Set BUDGET=0 for an
# unlimited run when your shell has no timeout.
BUDGET = float(os.environ.get("BUDGET", "90")) or float("inf")
PER_PAGE_LIMIT = int(os.environ.get("PER_PAGE_LIMIT", "100"))
MIN_BYTES = 25_000

# Sites behind a WAF often serve a JS interstitial to datacenter IPs. It clears
# on its own in a few seconds, but the page navigates out from under you while
# it does, so every evaluate() has to tolerate a destroyed execution context.
CHALLENGE_MARKERS = (
    "Checking your browser", "Just a moment", "Verifying you are human",
    "Enable JavaScript and cookies", "Attention Required", "DDoS protection",
)

# Overlays are the main thing that ruins these screenshots: a cookie banner or
# newsletter modal on one side but not the other makes the diff unreadable.
HIDE_CSS = """
[id*="onetrust"], #onetrust-consent-sdk, .onetrust-pc-dark-filter,
[class*="cookie-banner"], [class*="cookie-notice"], [id*="cookie-law"], [class*="cookieconsent"],
[id*="CybotCookiebot"], [class*="termly"], [class*="osano"], [class*="usercentrics"],
.klaviyo-form, [class*="kl-private"], [id^="attentive"], #attentive_overlay, [class*="attentive"],
[class*="modal-backdrop"], [class*="popup-overlay"], [id*="popupmaker"], [class*="pum-overlay"],
[class*="exit-intent"], [id*="gorgias"], [class*="drift-"], [id*="intercom"],
[class*="privy"], [id*="privy"], [class*="justuno"], [id*="ju_"],
[class*="wisepops"], [id*="wisepops"], [id*="hs-eu-cookie"], [class*="tidio"],
[id*="crisp-client"], [class*="zsiq"], [id*="livechat"], [class*="olark"],
iframe[title*="hat"], iframe[id*="chat"], iframe[title*="ookie"] { display: none !important; }
html { scroll-behavior: auto !important; }
*, *::before, *::after {
  animation-duration: 0s !important; animation-delay: 0s !important;
  transition-duration: 0s !important; caret-color: transparent !important;
}
"""

ACCEPT_TEXTS = ["Accept All", "Accept all cookies", "Accept Cookies", "Allow all",
                "Accept", "I Agree", "Agree", "Got it", "OK"]


class Timeout(Exception):
    pass


@contextmanager
def hard_timeout(seconds):
    """Playwright calls can wedge in ways their own timeouts don't cover
    (challenge loops, infinite-scroll pages). SIGALRM is the backstop."""
    def handler(signum, frame):
        raise Timeout(f"exceeded {seconds}s")
    old = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def js(page, expr, default=None):
    for _ in range(2):
        try:
            return page.evaluate(expr)
        except Timeout:
            raise
        except Exception:
            try:
                page.wait_for_timeout(600)
            except Exception:
                pass
    return default


def style(page):
    for _ in range(3):
        try:
            page.add_style_tag(content=HIDE_CSS)
            return
        except Timeout:
            raise
        except Exception:
            page.wait_for_timeout(600)


def wait_past_challenge(page, min_height, timeout_s=45):
    deadline = time.time() + timeout_s
    reloaded = False
    while time.time() < deadline:
        txt = js(page, "document.body ? document.body.innerText.slice(0,400) : ''", "")
        h = js(page, "document.body ? document.body.scrollHeight : 0", 0)
        if not any(m in txt for m in CHALLENGE_MARKERS) and h > min_height:
            return True
        page.wait_for_timeout(2000)
        if not reloaded and time.time() > deadline - timeout_s / 3:
            reloaded = True
            try:
                page.reload(wait_until="domcontentloaded", timeout=45000)
            except Exception:
                pass
    return False


def capture(page, url, path, min_height):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    if not wait_past_challenge(page, min_height):
        raise RuntimeError("bot challenge did not clear / page stayed empty")
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass

    for t in ACCEPT_TEXTS:
        try:
            btn = page.get_by_role("button", name=t, exact=False).first
            if btn.is_visible(timeout=700):
                btn.click(timeout=2000)
                page.wait_for_timeout(500)
                break
        except Exception:
            pass

    style(page)

    # Step down the page so lazy-loaded images and on-scroll reveals actually
    # render; a full_page screenshot alone leaves them blank or half-faded.
    height = js(page, "document.body.scrollHeight", 0) or 0
    y, step = 0, 800
    while y < height and y < 45000:
        js(page, f"window.scrollTo(0, {y})")
        page.wait_for_timeout(170)
        y += step
        height = js(page, "document.body.scrollHeight", height) or height
    js(page, "window.scrollTo(0, 0)")
    page.wait_for_timeout(1000)

    js(page, """(() => {
        document.querySelectorAll('img[loading="lazy"]').forEach(i => { i.loading = 'eager'; });
        document.querySelectorAll('img[data-src]').forEach(i => { if (!i.src) i.src = i.dataset.src; });
        document.querySelectorAll('video').forEach(v => {
            try { v.pause(); if (!v.currentTime) v.currentTime = 0.1; } catch (e) {}
        });
    })()""")
    page.wait_for_timeout(900)
    style(page)

    final_h = js(page, "document.body.scrollHeight", 0) or 0
    if final_h < min_height:
        raise RuntimeError(f"page looks empty (height {final_h})")
    page.screenshot(path=path, full_page=True, animations="disabled")
    return final_h


def shot_path(out, slug, vp_id, side):
    return f"{out}/{slug}-{vp_id}-{side}.png"


def is_done(out, slug, vp_id, side):
    f = shot_path(out, slug, vp_id, side)
    return os.path.exists(f) and os.path.getsize(f) >= MIN_BYTES


def main():
    cfg = json.load(open(sys.argv[1]))
    out = cfg.get("out", "/tmp/shots")
    os.makedirs(out, exist_ok=True)
    pages = cfg["pages"]
    viewports = cfg.get("viewports") or [{"id": "desktop", "width": 1440, "height": 1000}]
    auth = cfg.get("auth") or {}
    sides = [("before", cfg["before"]["base"].rstrip("/")),
             ("after", cfg["after"]["base"].rstrip("/"))]

    manifest_path = f"{out}/manifest.json"
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else []
    have = {(m["slug"], m["viewport"], m["side"]) for m in manifest}

    start = time.time()
    budget_hit = False

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--hide-scrollbars", "--force-device-scale-factor=1"])
        for vp in viewports:
            if budget_hit:
                break
            for side, base in sides:
                if budget_hit:
                    break
                todo = [pg for pg in pages if not is_done(out, pg["slug"], vp["id"], side)]
                if not todo:
                    continue

                ctx_args = {
                    "viewport": {"width": vp["width"], "height": vp["height"]},
                    "device_scale_factor": cfg.get("scale", 1),
                    "locale": "en-US",
                    "is_mobile": bool(vp.get("mobile")),
                    "has_touch": bool(vp.get("mobile")),
                    "user_agent": (
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                        "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
                        if vp.get("mobile") else
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
                }
                basic = (auth.get(side) or {}).get("basic") or auth.get("basic")
                if basic:
                    ctx_args["http_credentials"] = {"username": basic["username"],
                                                    "password": basic["password"]}
                ctx = browser.new_context(**ctx_args)
                for c in (auth.get(side) or {}).get("cookies", []) or auth.get("cookies", []):
                    try:
                        ctx.add_cookies([c])
                    except Exception:
                        pass

                pg_obj = ctx.new_page()
                pg_obj.set_default_timeout(25000)

                # One warm-up hit so the challenge cookie is set for the rest.
                try:
                    with hard_timeout(60):
                        pg_obj.goto(base + "/", wait_until="domcontentloaded", timeout=45000)
                        wait_past_challenge(pg_obj, cfg.get("min_height", 600))
                except Exception as e:
                    print(f"WARM {side}/{vp['id']} {type(e).__name__}: {str(e)[:80]}", flush=True)

                for pgdef in pages:
                    slug = pgdef["slug"]
                    # before_path lets you pair pages whose URL changed in the migration.
                    path = pgdef.get("before_path", pgdef["path"]) if side == "before" else pgdef["path"]
                    if is_done(out, slug, vp["id"], side):
                        key = (slug, vp["id"], side)
                        if key not in have:
                            manifest.append({"slug": slug, "title": pgdef["title"], "path": path,
                                             "side": side, "viewport": vp["id"],
                                             "url": base + path, "height": 0,
                                             "bytes": os.path.getsize(shot_path(out, slug, vp["id"], side))})
                            have.add(key)
                        continue
                    if time.time() - start > BUDGET:
                        budget_hit = True
                        print("BUDGET reached — run again to continue", flush=True)
                        break

                    fn = shot_path(out, slug, vp["id"], side)
                    url = base + path
                    for attempt in (1, 2):
                        try:
                            with hard_timeout(PER_PAGE_LIMIT):
                                h = capture(pg_obj, url, fn, cfg.get("min_height", 600))
                            kb = os.path.getsize(fn) // 1024
                            print(f"OK   {side:6s} {vp['id']:7s} {slug:26s} h={h:6d} {kb}KB", flush=True)
                            manifest.append({"slug": slug, "title": pgdef["title"], "path": path,
                                             "side": side, "viewport": vp["id"], "url": url,
                                             "height": h, "bytes": os.path.getsize(fn)})
                            have.add((slug, vp["id"], side))
                            break
                        except Exception as e:
                            print(f"RETRY{attempt} {side:6s} {vp['id']:7s} {slug:26s} "
                                  f"{type(e).__name__}: {str(e)[:80]}", flush=True)
                            if os.path.exists(fn) and os.path.getsize(fn) < MIN_BYTES:
                                os.remove(fn)
                            time.sleep(3)
                    else:
                        print(f"FAIL {side:6s} {vp['id']:7s} {slug:26s} gave up", flush=True)
                ctx.close()
        browser.close()

    seen, dedup = set(), []
    for m in manifest:
        k = (m["slug"], m["viewport"], m["side"])
        if k not in seen:
            seen.add(k)
            dedup.append(m)
    with open(manifest_path, "w") as f:
        json.dump(dedup, f, indent=2)

    remaining = [f"{pg['slug']}-{vp['id']}-{side}"
                 for vp in viewports for side, _ in sides for pg in pages
                 if not is_done(out, pg["slug"], vp["id"], side)]
    print(f"REMAINING {len(remaining)}" + (": " + " ".join(remaining[:12]) if remaining else ""),
          flush=True)


main()
