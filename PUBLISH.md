# How to publish this on GitHub (and get a public website)

You'll end up with:

- a public repo — `https://github.com/<you>/<repo>`
- a public dashboard — `https://<you>.github.io/<repo>/`
- a GitHub Action that re-fetches the numbers and updates that dashboard on its own

Pick **one** route below. Route A is the fastest; Route C needs no terminal at all.

---

## Step 0 — get the files onto your Mac

Download **`seva-submission-tracker.zip`** from this workspace, then in Terminal:

```bash
cd ~/Downloads
unzip seva-submission-tracker.zip
cd seva-submission-tracker
```

Check it's the right folder — you should see `server.py`, `README.md`, `docs/`:

```bash
ls
```

Want to see it running before you publish? Two commands, no installs:

```bash
python3 -m http.server 8000 --directory docs     # static preview → http://localhost:8000
# or, with live data + working filters:
python3 server.py                                # → http://localhost:8000
```

---

## Route A — one command (recommended)

Needs the GitHub CLI. If you don't have it:

```bash
brew install gh
gh auth login          # choose GitHub.com → HTTPS → login with a browser
```

Then, from inside the project folder:

```bash
./scripts/publish.sh
```

It asks for your username and a repo name, then does everything: creates the repo,
pushes, turns on Pages, and gives the refresh Action permission to commit. Done —
your site is at `https://<you>.github.io/<repo>/` in 1–3 minutes.

You can also skip the questions:

```bash
./scripts/publish.sh git@github.com:<you>/seva-submission-tracker.git --create
```

---

## Route B — plain git (no gh CLI)

**1. Create an empty repo on GitHub**

github.com → **+** (top right) → **New repository** → name it `seva-submission-tracker`
→ **Public** → do **not** tick "Add a README" → **Create repository**.
Copy the URL it shows (e.g. `https://github.com/you/seva-submission-tracker.git`).

**2. Push your copy**

```bash
cd ~/Downloads/seva-submission-tracker
git init -b main
git add -A
git commit -m "Seva submission tracker"
git remote add origin https://github.com/<you>/seva-submission-tracker.git
git push -u origin main
```

When it asks for a password, **your GitHub password will not work** — paste a
**Personal Access Token** instead: github.com → Settings → Developer settings →
Personal access tokens → **Tokens (classic)** → Generate new token → tick **`repo`**
→ copy it → paste as the password.
(Easier alternative: `git remote set-url origin git@github.com:<you>/seva-submission-tracker.git` after adding an SSH key.)

**3. Switch the website on**

Repo → **Settings** → **Pages** → *Source*: **Deploy from a branch** →
*Branch*: **main**, *Folder*: **`/docs`** → **Save**.

**4. Let the auto-refresh Action write**

Repo → **Settings** → **Actions** → **General** → *Workflow permissions* →
**Read and write permissions** → **Save**.

---

## Route C — no terminal at all (browser only)

1. Create the empty repo as in Route B step 1.
2. Unzip the download, then open the repo page in your browser and click
   **Add file → Upload files**.
3. Drag in **everything**: `docs`, `scripts`, `templates`, `data`, `server.py`,
   `README.md`, `LICENSE`, `requirements.txt`, `.gitignore` and `.github`.
   On macOS, press **⌘ ⇧ .** in Finder to reveal the dot-folders (`.github`, `.gitignore`) —
   without them the auto-refresh won't work.
4. Type a commit message → **Commit changes**.
5. Then do Route B steps 3 and 4 (Pages + Action permissions) — both are just dropdowns.

---

## Check it worked

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://<you>.github.io/<repo>/
```

`200` = live. In the browser you should see the dashboard with **Submissions received**
and a working **Participant count by sub-theme** panel with Category/Sector dropdowns.

To populate fresh numbers immediately: repo → **Actions** tab → *Refresh snapshot* →
**Run workflow**. It commits a new snapshot, and the site updates about a minute later.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Site 404s after 5 minutes | Settings → Pages → make sure *Source* = Deploy from a branch, branch `main`, folder `/docs` (not `/root`) |
| Pages section is empty / "upgrade required" | Pages on private repos needs GitHub Pro — make the repo **Public** |
| Action fails: `Permission denied` / 403 | Settings → Actions → General → Workflow permissions → **Read and write** |
| Action runs but says "no changes to commit" | Nothing moved upstream since the last run — that's success, not an error |
| Numbers frozen on the site | The Action's schedule needs the repo to have had *some* activity; also check the Actions tab for a failed run, and hit **Run workflow** |
| `git push` asks for a password | Use a Personal Access Token (Route B step 2), or switch to SSH |
| `gh: command not found` | `brew install gh` then `gh auth login` |
| `python3: command not found` | Install Python 3 (`brew install python3`) or use Route C |
| Want to stop the auto-refresh | Delete `.github/workflows/refresh.yml` (or Actions tab → Refresh snapshot → ⋯ → Disable workflow) |

---

## Updating a site you've already published

If you've updated files in your local clone:

```bash
git add -A
git commit -m "fix: clearer static-hosting message"
git push
```

If you don't have a local clone yet:

```bash
git clone https://github.com/tejuas98/track-the-num.git
cd track-the-num
# copy modified files in
git add -A
git commit -m "update site"
git push
```

---

## What gets published, and what doesn't

Published: the dashboard (`docs/`), the scripts, the tracked history (`data/history.jsonl`)
and the workflow.

Not published: nothing sensitive — the project holds no keys or tokens, because the
challenge's analytics API is public and needs no login. (That itself is worth flagging to
the organisers: their participant data is readable by anyone who knows the URL.)

Heads-up on ownership: this is an **unofficial** mirror of the organisers' data. The README
says so; keep it that way, and don't present the numbers as official.
