#!/usr/bin/env python3
"""Seva tracker server - serves the dashboard and proxies the analytics API.

Why a proxy: the analytics API sends no CORS headers, so a browser cannot call it
from another origin. This server fetches upstream (server-side) and serves it
same-origin, which also lets the page auto-refresh every 60s.

Routes
  GET  /                      -> docs/index.html (baked snapshot renders instantly)
  GET  /api/live/snapshot     -> fresh snapshot JSON (cached LIVE_TTL seconds)
  GET  /api/live/quick         -> headline counters only (cached QUICK_TTL seconds)
  GET  /api/live/subthemes     -> sub-theme counts for any ?category=&sector= (computed on demand)
  GET  /api/live/districts    -> upstream district tracker pass-through (?state=...&category=...&sector=...)
  GET  /api/history           -> tracked history rows
  POST /api/refresh           -> force a refresh of snapshot + history
  GET  /api/health            -> this server + upstream health

Run:  python3 server.py            (env PORT, default 8000; ANALYTICS_BASE to override upstream)
"""
import datetime, json, os, sys, time, threading, urllib.request, urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(ROOT, "docs")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import fetch_snapshot as fs  # noqa: E402
import filters as F          # noqa: E402

PORT = int(os.environ.get("PORT", "8000"))
LIVE_TTL = int(os.environ.get("LIVE_TTL", "45"))     # seconds a full snapshot is reused
QUICK_TTL = int(os.environ.get("QUICK_TTL", "30"))   # seconds a light poll is reused
_cache = {"snap": None, "at": 0.0}
_qcache = {"snap": None, "at": 0.0}
_lock = threading.Lock()
_qlock = threading.Lock()

# light poll: 4 small upstream calls instead of ~20, so the dashboard can refresh
# every minute without leaning on the challenge's API
QUICK_ENDPOINTS = ("submissions", "teams", "registrations", "overview")


def live_snapshot(force=False):
    with _lock:
        age = time.time() - _cache["at"]
        if not force and _cache["snap"] and age < LIVE_TTL:
            return _cache["snap"], age
        # matrix=False: the baked filter matrix comes from docs/data/snapshot.json,
        # and any Category+Sector pair is computed on demand by /api/live/subthemes
        snap = fs.build_snapshot(quiet=True, matrix=False)
        rows = fs.append_history(fs.history_row(snap))
        snap["history"] = rows[-400:]
        _cache["snap"] = snap
        _cache["at"] = time.time()
        try:  # also keep the static build fresh so a plain reload works without the server
            json.dump(snap, open(os.path.join(DOCS, "data", "snapshot.json"), "w"), indent=1)
        except OSError:
            pass
        return snap, 0.0


def quick_snapshot(force=False):
    """Cheap freshness check for the headline counters (submissions, teams, registrations)."""
    with _qlock:
        age = time.time() - _qcache["at"]
        if not force and _qcache["snap"] and age < QUICK_TTL:
            return _qcache["snap"], age
        snap = {"generated_at": datetime.datetime.now(fs.IST).isoformat(timespec="seconds"),
                "base": fs.BASE, "quick": True}
        for ep in QUICK_ENDPOINTS:
            try:
                snap[ep] = fs.get(f"/api/analytics/{ep}").get("result")
            except Exception:
                snap[ep] = None
        _qcache["snap"], _qcache["at"] = snap, time.time()
        return snap, 0.0


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DOCS, **kw)

    def log_message(self, fmt, *args):                    # quieter logs
        if "/api/live" not in self.path:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

        if path == "/api/health":
            up = {}
            try:
                with urllib.request.urlopen(fs.BASE + "/api/health", timeout=15) as r:
                    up = json.load(r).get("result", {})
            except Exception as e:
                up = {"error": str(e)}
            return self._json({"server": "ok", "upstream": "ok" if "error" not in up else "unreachable",
                               "upstream_detail": up, "base": fs.BASE})

        if path == "/api/live/snapshot":
            try:
                snap, age = live_snapshot()
                self._json({"cached_age_seconds": round(age, 1), **snap})
            except Exception as e:
                return self._json({"error": str(e)}, 502)

        if path == "/api/live/quick":
            try:
                snap, age = quick_snapshot()
                self._json({"cached_age_seconds": round(age, 1), **snap})
            except Exception as e:
                return self._json({"error": str(e)}, 502)

        if path == "/api/live/subthemes":
            cat = (qs.get("category") or [F.ALL])[0]
            sec = (qs.get("sector") or [F.ALL_SECTORS])[0]
            try:
                res = fs.evaluate_combo(cat, sec)
                return self._json({"category": cat, "sector": sec,
                                   "summary": res["summary"], "rows": res["counts"],
                                   "spellings": res["spellings"],
                                   "generated_at": datetime.datetime.now(fs.IST).isoformat(timespec="seconds")})
            except Exception as e:
                return self._json({"error": str(e), "category": cat, "sector": sec}, 502)

        if path == "/api/live/districts":
            params = {k: v[0] for k, v in qs.items() if k in ("state", "states", "category", "sector", "track", "timeRange")}
            try:
                res = fs.get("/api/analytics/districts" + ("?" + urllib.parse.urlencode(params) if params else "")).get("result")
                res["subthemes"] = fs.aggregate_problems(res)
                return self._json(res)
            except Exception as e:
                return self._json({"error": str(e)}, 502)

        if path == "/api/history":
            return self._json({"rows": fs.load_history(1000)})

        return super().do_GET()

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path == "/api/refresh":
            try:
                snap, _ = live_snapshot(force=True)
                return self._json({"ok": True, "generated_at": snap["generated_at"]})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 502)
        self.send_error(404)


def warm():
    try:
        live_snapshot(force=True)      # warm cache + record first history row
        print("warm-up complete", file=sys.stderr)
    except Exception as e:
        print(f"warm-up failed ({e}); serving the baked snapshot", file=sys.stderr)


if __name__ == "__main__":
    os.makedirs(DOCS, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    # serve immediately (the baked snapshot renders instantly); warm the live cache in the background
    threading.Thread(target=warm, daemon=True).start()
    print(f"serving {DOCS} on 0.0.0.0:{PORT} (upstream {fs.BASE})", flush=True)
    server.serve_forever()
