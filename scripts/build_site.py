#!/usr/bin/env python3
"""Bake the current snapshot into docs/index.html so the site works with no server
(GitHub Pages, netlify drop, opening the file directly, or a sandboxed preview iframe).

Usage: python3 scripts/build_site.py
"""
import json, os, re, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "templates", "dashboard.html")
SNAPSHOT = os.path.join(ROOT, "docs", "data", "snapshot.json")
OUT = os.path.join(ROOT, "docs", "index.html")
MARKER = "__SNAPSHOT_JSON__"


def main():
    if not os.path.exists(SNAPSHOT):
        raise SystemExit("docs/data/snapshot.json missing - run scripts/fetch_snapshot.py first")

    snap = json.load(open(SNAPSHOT))
    # </script> inside the JSON would break the inline script tag
    payload = json.dumps(snap, separators=(",", ":")).replace("</", "<\\/")

    html = open(TEMPLATE).read()
    if MARKER not in html:
        raise SystemExit(f"template marker {MARKER} not found in {TEMPLATE}")
    html = html.replace(MARKER, payload)
    html = html.replace("<title>", f"<!-- built {datetime.datetime.now().isoformat(timespec='seconds')} -->\n<title>", 1)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write(html)
    print(f"built {OUT}  ({len(html)/1024:.0f} KB, snapshot {snap['generated_at']})")


if __name__ == "__main__":
    main()
