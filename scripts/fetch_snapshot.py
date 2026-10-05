#!/usr/bin/env python3
"""Pull the Seva First Innovation Challenge analytics API into one snapshot file.

Writes:
  docs/data/snapshot.json   - everything the dashboard needs (also baked into docs/index.html)
  data/history.jsonl        - one metrics row appended per run (this is what makes tracking possible)

Usage:
  python3 scripts/fetch_snapshot.py              # axes only (fast, ~30s)
  python3 scripts/fetch_snapshot.py --matrix     # + every Category x Sector combination (~1-2 min)
  python3 scripts/fetch_snapshot.py --no-matrix  # force axes only
Env:
  ANALYTICS_BASE   upstream base URL
  BAKE_MATRIX=1    bake the full matrix (default when neither flag is given)
  FETCH_WORKERS    parallel upstream requests (default 5)
"""
import concurrent.futures as futures
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import filters as F  # noqa: E402

BASE = os.environ.get("ANALYTICS_BASE", "https://09kbhlpur8.execute-api.ap-south-1.amazonaws.com")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
WORKERS = int(os.environ.get("FETCH_WORKERS", "5"))

ENDPOINTS = ["dashboard", "overview", "registrations", "submissions", "teams", "themes",
             "geography", "colleges", "trends", "demographics", "channels"]

# district tracker for the district table / map section
DISTRICTS = {
    "all": {},
    "maharashtra": {"state": "Maharashtra"},
    "gen": {"category": "General Category"},
    "women": {"sector": "Women & Child"},
}

DISTRICT_KEEP = ("district", "state", "registrations", "team_lead_and_team_member",
                 "applications", "pitch_decks", "share_percent", "application_rate_percent")
GEO_KEEP = ("filters", "total_participants", "selected_state", "state_breakdown",
            "zonal_distribution", "top_metro_cities")

# combinations that get baked into the static site
def combos_to_bake(matrix=True):
    out = [(F.ALL, F.ALL_SECTORS)]
    out += [(c, F.ALL_SECTORS) for c in F.CATEGORY_LABELS if c != F.ALL]
    out += [(F.ALL, s) for s in F.SECTOR_LABELS if s != F.ALL_SECTORS]
    if matrix:
        out += [(c, s) for c in F.CATEGORY_LABELS if c != F.ALL
                        for s in F.SECTOR_LABELS if s != F.ALL_SECTORS]
    seen, uniq = set(), []
    for pair in out:
        k = F.combo_key(*pair)
        if k not in seen:
            seen.add(k); uniq.append(pair)
    return uniq


def get(path, timeout=90):
    req = urllib.request.Request(BASE + path,
                                 headers={"User-Agent": "seva-tracker/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def aggregate_problems(districts_result):
    """Sum problem-statement (= sub-theme) counts across districts for one upstream response."""
    agg = {}
    for rec in districts_result.get("districts", []):
        for p in (rec.get("problem_statements") or {}).get("problems") or []:
            k = (p.get("title") or "").strip()
            agg[k] = agg.get(k, 0) + p.get("count", 0)
    return agg


def fetch_districts(params):
    url = "/api/analytics/districts" + (("?" + urllib.parse.urlencode(params)) if params else "")
    return get(url).get("result") or {}


def evaluate_combo(category_label, sector_label):
    """Fetch every spelling variant of a Category x Sector combo and merge the sub-theme counts."""
    pairs = F.resolve(category_label, sector_label)
    counts, apps, decks, regs = {}, 0, 0, 0
    for cval, sval in pairs:
        params = {}
        if cval:
            params["category"] = cval
        if sval:
            params["sector"] = sval
        res = fetch_districts(params)
        for k, v in aggregate_problems(res).items():
            counts[k] = counts.get(k, 0) + v
        s = res.get("summary") or {}
        apps += s.get("applications_completed") or 0
        decks += s.get("pitch_decks_received") or 0
        regs = max(regs, s.get("total_registrations") or 0)
    return {
        "summary": {"total_registrations": regs, "applications_completed": apps,
                    "pitch_decks_received": decks},
        "counts": sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])),
        "spellings": [s for _, s in pairs if s] or [],
        "n_calls": len(pairs),
    }


def slim_districts(res):
    out = {k: v for k, v in res.items() if k != "districts"}
    out["districts"] = [{k: r.get(k) for k in DISTRICT_KEEP} for r in res.get("districts", [])]
    return out


def build_snapshot(quiet=False, matrix=True):
    snap = {"generated_at": datetime.datetime.now(IST).isoformat(timespec="seconds"), "base": BASE}

    for ep in ENDPOINTS:
        try:
            res = get(f"/api/analytics/{ep}").get("result")
            if ep == "geography" and isinstance(res, dict):
                res = {k: v for k, v in res.items() if k in GEO_KEEP}
            snap[ep] = res
        except Exception as e:
            snap[ep] = None
            if not quiet:
                print(f"  ! {ep}: {e}", file=sys.stderr)

    # --- district tracker block (used by the district table) ---
    snap["districts"] = {"by_state": {}}
    for key, params in DISTRICTS.items():
        try:
            res = fetch_districts(params)
        except Exception as e:
            if not quiet:
                print(f"  ! districts[{key}]: {e}", file=sys.stderr)
            continue
        res["subthemes"] = sorted(aggregate_problems(res).items(), key=lambda kv: -kv[1])
        snap["districts"][key] = slim_districts(res)

    # --- baked Category x Sector matrix for the sub-theme explorer ---
    jobs = combos_to_bake(matrix)
    results = {}
    with futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(evaluate_combo, c, s): (c, s) for c, s in jobs}
        for fut in futures.as_completed(futs):
            c, s = futs[fut]
            try:
                results[F.combo_key(c, s)] = fut.result()
            except Exception as e:
                if not quiet:
                    print(f"  ! combo {c} / {s}: {e}", file=sys.stderr)

    names = []
    index = {}
    combos = {}
    for key, res in results.items():
        compact = []
        for name, cnt in res["counts"]:
            if name not in index:
                index[name] = len(names); names.append(name)
            compact.append([index[name], cnt])
        combos[key] = {"s": [res["summary"]["total_registrations"],
                             res["summary"]["applications_completed"],
                             res["summary"]["pitch_decks_received"]],
                       "c": compact}
    spellings = {}
    for key in combos:
        c, s_ = key.split("||")
        v = F.resolve(c, s_)
        vals = [x for _, x in v if x]
        if len(vals) > 1:
            spellings[key] = vals
    snap["subtheme_explorer"] = {
        "categories": F.CATEGORY_LABELS,
        "sectors": F.SECTOR_LABELS,
        "subtheme_names": names,
        "combos": combos,
        "spellings": spellings,
        "matrix_baked": bool(matrix),
    }
    return snap


def history_row(snap):
    sub = snap.get("submissions") or {}
    teams = snap.get("teams") or {}
    regs = snap.get("registrations") or {}
    dist = (snap.get("districts") or {}).get("all") or {}
    summ = dist.get("summary") or {}
    return {
        "ts": snap["generated_at"],
        "submissions": sub.get("total_submissions"),
        "team_submissions": sub.get("total_team_submissions"),
        "remaining": sub.get("remaining_submissions"),
        "rate": sub.get("submission_rate_percent"),
        "applications": summ.get("applications_completed"),
        "pitch_decks": summ.get("pitch_decks_received"),
        "registrations": regs.get("total_registrations"),
        "teams": teams.get("total_teams"),
        "unteamed": teams.get("unteamed_participants"),
    }


def append_history(row, keep=2000):
    path = os.path.join(ROOT, "data", "history.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    if rows and rows[-1]["ts"][:16] == row["ts"][:16]:
        rows[-1] = row
    else:
        rows.append(row)
    rows = rows[-keep:]
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return rows


def load_history(limit=400):
    path = os.path.join(ROOT, "data", "history.jsonl")
    if not os.path.exists(path):
        return []
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows[-limit:]


def main():
    args = sys.argv[1:]
    quiet = "--quiet" in args
    if "--matrix" in args:
        matrix = True
    elif "--no-matrix" in args:
        matrix = False
    else:
        matrix = os.environ.get("BAKE_MATRIX", "1") not in ("0", "false", "no")

    snap = build_snapshot(quiet=quiet, matrix=matrix)
    rows = append_history(history_row(snap))
    snap["history"] = rows[-400:]

    out = os.path.join(ROOT, "docs", "data", "snapshot.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(snap, f, separators=(",", ":"))

    if not quiet:
        s = snap.get("submissions") or {}
        d = (snap.get("districts") or {}).get("all") or {}
        regs = snap.get("registrations") or {}
        ex = snap["subtheme_explorer"]
        print(f"snapshot {snap['generated_at']}")
        print(f"  submissions      : {s.get('total_submissions')} of "
              f"{(s.get('total_submissions') or 0) + (s.get('remaining_submissions') or 0)}"
              f"  ({s.get('submission_rate_percent')}% done)")
        print(f"  team submissions : {s.get('total_team_submissions')}")
        print(f"  applications     : {(d.get('summary') or {}).get('applications_completed')}")
        print(f"  registrations    : {regs.get('total_registrations')}")
        print(f"  explorer         : {len(ex['combos'])} category x sector combos"
              f"{' (full matrix)' if ex['matrix_baked'] else ' (axes only)'},"
              f" {len(ex['subtheme_names'])} sub-themes")
        print(f"  history rows     : {len(rows)}")
        print(f"  written          : {out}  ({os.path.getsize(out)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
