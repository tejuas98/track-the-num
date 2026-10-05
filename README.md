# Seva First Innovation Challenge — Submission Tracker

A self-hosted dashboard for tracking **how many submissions have come in** for the
Seva First Innovation Challenge (Maharashtra Zone) — built because the challenge site's
own *“Participant count by sub-theme”* dialog fails to load.

The site's dialog breaks because the sub-theme-counts route it calls doesn't exist on the
analytics backend. **The backend itself is healthy** (`/api/health` → database connected),
and its other routes return plenty of data — so this tracker reads those routes directly.

![snapshot: 381 submissions · 36.9% complete](https://img.shields.io/badge/submissions-381-blue)
![registrations](https://img.shields.io/badge/registrations-1%2C570-green)

## Quick start

```bash
python3 scripts/fetch_snapshot.py     # pull the latest numbers -> docs/data/snapshot.json + data/history.jsonl
python3 scripts/build_site.py         # bake them into docs/index.html (self-contained, no server needed)
python3 server.py                     # optional: live server + API proxy on http://localhost:8000
```

No dependencies — Python standard library only. Python 3.8+.

## Two ways to use it

| Mode | How | Freshness | Notes |
|---|---|---|---|
| **Live** | `python3 server.py` → open `http://localhost:8000` | headline counters every **60s**, full snapshot every **10 min** (Refresh now = immediate) | Server proxies the analytics API (it sends no CORS headers, so a browser can't call it directly). Light polls hit 4 small upstream endpoints; full refreshes hit ~20. |
| **Static** | open `docs/index.html`, or host `docs/` on GitHub Pages / Netlify / any static host | last baked snapshot; the Action re-fetches **hourly** | Refreshed by the GitHub Action, by re-running the two scripts, or by pushing. Nothing runs in the visitor's browser. |

### How fresh is the data, really?

Measured on 5 Oct 2026: registrations went **1,570 → 1,571** and teams **493 → 494**
inside a 3-minute window, so the analytics backend tracks the live challenge database and
students' registrations/submissions show up within minutes. Freshness is therefore limited by
*how often you pull*, not by the source:

| You want | Set up |
|---|---|
| Seconds-level, while your laptop is on | `python3 server.py` (already polls per minute) |
| Always-on, no laptop | host `server.py` on any small always-on box (Render/Railway/VPS) and hit it from the browser |
| Public page, no server | GitHub Pages + tighten the Action cron (e.g. `*/30 * * * *`). GitHub delays scheduled runs, so treat it as "roughly hourly". |

## Publish it on GitHub Pages

> **New here? Follow [PUBLISH.md](PUBLISH.md) — it has three routes (one-command, plain git, and browser-only) plus troubleshooting.**

Fastest way — the publish script creates the repo, pushes, and switches Pages on:

```bash
brew install gh && gh auth login     # once
./scripts/publish.sh                 # asks for username + repo name, then does the rest
```

Or by hand:

```bash
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

Then **Settings → Pages → Source: Deploy from a branch → Branch: `main`, Folder: `/docs`**.
Your dashboard is live at `https://<you>.github.io/<repo>/`.

The included workflow (`.github/workflows/refresh.yml`) re-fetches the numbers and commits
`docs/` on a schedule, so the Pages site updates itself. Turn it on by pushing the repo —
no secrets needed (the analytics API is public; see *Security note* below).

## Filtering (mirrors the site's own dialog)

The **Participant count by sub-theme** panel now reproduces the filters from the challenge site's
broken dialog — and they actually work:

| Control | Options | Notes |
|---|---|---|
| **Search Sub-themes** | free text | matches sub-theme title; typing a sector name shows that whole sector |
| **Category** | All categories, Women Category, Age below 18, Age below 21, General Category | |
| **Sector** | All sectors, Agriculture, Law and Order, Women and Child, Urban Development, Health and Medical, Defence, Education and Employability, Emerging Technologies, Infrastructure and Mobility, Sustainability, Other | |
| **Metric** | Applications / Registrations | Category+Sector only apply to Applications; the API reports registrations as one combined figure |
| **Sort** | Highest first, Lowest first, A–Z, Z–A | |
| **Reset** | — | back to All / All, Applications, Highest first |

Footer reads like the original: *“5 sub-themes · 32 applications in All categories · Women and Child”*.

**Two things worth knowing:**

1. **Some sectors are stored twice.** The database holds e.g. `Women & Child` *and* `Women and Child`
   as separate values (20 vs 12 applications), same for `Health and Medical`/`Health & Medical`,
   `Law and Order`/`Law & Order`, `Infrastructure...`. Each dropdown option merges every spelling, so the
   numbers are complete — the UI flags it with a “counts are merged” note.
2. **How each combination is served.** Static builds bake all **60 Category × Sector combinations**
   (~2 min, `--matrix`, what the GitHub Action runs). The live server also computes any pair on demand
   via `/api/live/subthemes?category=…&sector=…` (~5 s). A combination missing from a snapshot and with
   no server running shows an explanation instead of an endless spinner.

## What it shows

- **Submission counters** — submissions received, expected total, remaining, % complete
- **Applications / pitch decks** — the district-tracker counters (the pitch-deck number matches team submissions)
- **Registrations, teams formed, solo teams, participants without a team**
- **Participant count by sub-theme** — registrations per sub-theme, plus breakdowns filtered by
  Women & Child sector, General Category, and Maharashtra
- **District-wise tracker** — 74 districts with registrations / applications / pitch decks, filterable + searchable
- **Daily registrations & teams**, state distribution, top sub-themes
- **History / deltas** — every refresh appends a row to `data/history.jsonl`; the dashboard plots the trend and shows growth since tracking began

## Layout

```
server.py                     live server + API proxy + history endpoint
scripts/fetch_snapshot.py     pulls the analytics API, bakes the filter matrix, writes snapshot + history
scripts/filters.py            canonical Category/Sector definitions incl. merged spellings
scripts/build_site.py         injects the snapshot into docs/index.html
templates/dashboard.html      the dashboard source (inline CSS/JS, no CDN, no build step)
docs/index.html               the built site  <-- GitHub Pages serves this
docs/data/snapshot.json       latest raw snapshot (machine-readable)
docs/reports/                 point-in-time HTML reports
data/history.jsonl            append-only metrics history (this is your tracking data)
```

## Data endpoints used

Base: `https://09kbhlpur8.execute-api.ap-south-1.amazonaws.com`

| Endpoint | Used for |
|---|---|
| `/api/health` | service + database health |
| `/api/analytics/submissions` | submission counter (site's “submissions” number) |
| `/api/analytics/dashboard`, `/overview` | KPIs incl. teams, trends |
| `/api/analytics/registrations`, `/teams` | registration & team rollups + daily series |
| `/api/analytics/themes` | registrations per sub-theme |
| `/api/analytics/districts` | district tracker; supports `?state=` `?category=` `?sector=` — the filter matrix is built from this |
| `/api/analytics/geography`, `/colleges`, `/trends`, `/demographics`, `/channels` | supporting breakdowns |

### Caveats worth knowing

- **Two submission counters exist.** `submissions.total_submissions` (381 at the time of writing,
  “expected total” = received + remaining) and the district tracker's `applications_completed` (911) /
  `pitch_decks_received` (182). Quote the one your audience expects; the dashboard shows both.
- **The dialog's default filter is empty.** `Category = General Category` + `Sector = Women and Child`
  currently holds **0 records** — Women & Child work is filed under the Women category/sector.
  Use the *Women & Child* tab instead.
- **`overview` and `dashboard` can differ by a minute** (separate upstream queries) — the dashboard
  prefers the `dashboard` values for teams and `submissions` for the submission counters.

### Security note

The analytics API currently answers **without any authentication or API key** — everything above is
readable by anyone with the URL, including participant-level rollups. This tracker only reads the
aggregate endpoints, but the upstream API should be put behind auth by its owners.

## Licence

MIT — see `LICENSE`. Data belongs to the challenge organisers; this tracker is an unofficial read-only mirror.
