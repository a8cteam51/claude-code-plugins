#!/usr/bin/env python3
"""Track progress and decisions for one migration.

    state.py --dir DIR status
    state.py --dir DIR next
    state.py --dir DIR done|skip|block|todo <step-id> ["note"]
    state.py --dir DIR decide <key> "<value>"
    state.py --dir DIR target --domain <temp domain> --blog-id <id>

After `decide` or `target`, re-run build_audit.py so the report and runbook pick the change up.
"""
import argparse
import datetime
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("command", choices=["status", "next", "done", "skip", "block", "todo", "decide", "target"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--domain")
    ap.add_argument("--blog-id")
    a = ap.parse_args()
    path = os.path.join(a.dir, "state.json")
    if not os.path.exists(path):
        sys.exit("No state.json in %s. Run build_audit.py first." % a.dir)
    state = json.load(open(path))
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    order = state.get("step_order", [])

    if a.command in ("status", "next"):
        todo = [s for s in order if state["steps"].get(s, {}).get("status", "todo") == "todo"]
        if a.command == "next":
            print(todo[0] if todo else "all steps done or skipped")
            return
        tally = {}
        for s in order:
            st = state["steps"].get(s, {}).get("status", "todo")
            tally[st] = tally.get(st, 0) + 1
        print("%s — %s" % (state.get("domain"), ", ".join("%d %s" % (n, k) for k, n in sorted(tally.items()))))
        for s in order:
            info = state["steps"].get(s, {})
            mark = {"done": "x", "skipped": "-", "blocked": "!"}.get(info.get("status"), " ")
            print("  [%s] %-34s %s" % (mark, s, info.get("note", "")))
        if state.get("decisions"):
            print("decisions:")
            for k, v in state["decisions"].items():
                print("  %s = %s" % (k, v.get("value") if isinstance(v, dict) else v))
        return

    if a.command == "decide":
        if len(a.args) < 2:
            sys.exit("usage: decide <key> <value>")
        state.setdefault("decisions", {})[a.args[0]] = {"value": " ".join(a.args[1:]), "at": now}
    elif a.command == "target":
        if not (a.domain and a.blog_id):
            sys.exit("usage: target --domain <domain> --blog-id <id>")
        state["target"] = {"domain": a.domain, "blog_id": int(a.blog_id), "at": now}
    else:
        if not a.args:
            sys.exit("usage: %s <step-id> [note]" % a.command)
        step = a.args[0]
        if step not in state["steps"]:
            sys.exit("unknown step %s" % step)
        status = {"done": "done", "skip": "skipped", "block": "blocked", "todo": "todo"}[a.command]
        state["steps"][step] = {"status": status, "at": now}
        if len(a.args) > 1:
            state["steps"][step]["note"] = " ".join(a.args[1:])
    json.dump(state, open(path, "w"), indent=2)
    print("recorded")


if __name__ == "__main__":
    main()
