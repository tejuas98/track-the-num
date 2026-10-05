#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Publish this tracker to GitHub and switch the website on.
#
# Usage
#   ./scripts/publish.sh                      # interactive: asks for your GitHub username + repo name
#   ./scripts/publish.sh <repo-url>           # push to a repo you already created
#   ./scripts/publish.sh <repo-url> --create  # also create the repo (needs the gh CLI, logged in)
#
# Examples
#   ./scripts/publish.sh git@github.com:yourname/seva-tracker.git --create
#   ./scripts/publish.sh https://github.com/yourname/seva-tracker.git
#
# What it does
#   1. git init (if this folder isn't a repo yet - e.g. you unzipped the download)
#   2. commits any pending changes
#   3. creates the GitHub repo (optional) and pushes
#   4. enables GitHub Pages  (main branch, /docs folder)
#   5. gives the refresh Action permission to commit  (only with gh CLI)
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."

REMOTE="${1:-}"
MODE="${2:-}"
BRANCH="main"

info() { printf '\033[1;34m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }

# ---------- 0. sanity: are we in the project? ----------
[ -f server.py ] && [ -d docs ] || die "Run this from the repo root (server.py + docs/ not found)."

HAVE_GH=0
command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1 && HAVE_GH=1

# ---------- 1. ask for the remote if not given ----------
if [ -z "$REMOTE" ]; then
  if [ "$HAVE_GH" = "1" ]; then
    GH_USER="$(gh api user --jq .login 2>/dev/null || echo "")"
    read -r -p "GitHub username [${GH_USER:-yourname}]: " ans_user
    GH_USER="${ans_user:-$GH_USER}"
    read -r -p "Repository name [seva-submission-tracker]: " ans_repo
    REPO="${ans_repo:-seva-submission-tracker}"
    [ -n "$GH_USER" ] || die "No username given."
    REMOTE="https://github.com/${GH_USER}/${REPO}.git"
    MODE="--create"
    info "Will create and push: ${GH_USER}/${REPO}"
  else
    echo "Paste the URL of the repo you created on github.com (e.g. https://github.com/you/seva-tracker.git)"
    read -r -p "repo url: " REMOTE
    [ -n "$REMOTE" ] || die "No URL given."
  fi
fi

# ---------- 2. make sure it's a git repo ----------
if [ ! -d .git ]; then
  info "No git repo here yet - initialising one (this is normal after unzipping the download)."
  git init -q -b "$BRANCH" 2>/dev/null || { git init -q; git checkout -q -b "$BRANCH" 2>/dev/null || true; }
fi
git config user.name  >/dev/null 2>&1 || git config user.name  "seva-tracker"
git config user.email >/dev/null 2>&1 || git config user.email "seva-tracker@users.noreply.github.com"

# ---------- 3. commit whatever is pending ----------
git add -A
if ! git diff --cached --quiet; then
  git commit -q -m "chore: snapshot before publish ($(date +%Y-%m-%d))"
  info "Committed pending changes."
fi
[ -n "$(git log --oneline -1 2>/dev/null)" ] || git commit -q --allow-empty -m "chore: initial commit"

# ---------- 4. create the repo (needs gh) and/or push ----------
if [ "$MODE" = "--create" ]; then
  [ "$HAVE_GH" = "1" ] || die "--create needs the GitHub CLI (gh). Install it: brew install gh && gh auth login"
  REPO_NAME="$(basename "$REMOTE" .git)"
  if gh repo view "$REMOTE" >/dev/null 2>&1; then
    info "Repo already exists - just pushing."
    git remote get-url origin >/dev/null 2>&1 && git remote set-url origin "$REMOTE" || git remote add origin "$REMOTE"
    git push -u origin "$BRANCH"
  else
    gh repo create "$REPO_NAME" --public --source=. --remote=origin --push
  fi
else
  git remote get-url origin >/dev/null 2>&1 && git remote set-url origin "$REMOTE" || git remote add origin "$REMOTE"
  git branch -M "$BRANCH" 2>/dev/null || true
  git push -u origin "$BRANCH"
fi

# ---------- 5. work out the Pages URL ----------
SLUG="$(git remote get-url origin | sed -E 's#^(git@github.com:|https://github.com/)##; s#\.git$##')"
OWNER="${SLUG%%/*}"; NAME="${SLUG##*/}"
PAGES_URL="https://${OWNER}.github.io/${NAME}/"

# ---------- 6. enable Pages + Action write access (gh only) ----------
if [ "$HAVE_GH" = "1" ]; then
  info "Turning on GitHub Pages (branch ${BRANCH}, folder /docs)..."
  sleep 3
  if gh api -X POST "repos/${SLUG}/pages" \
       -f "source[branch]=${BRANCH}" -f "source[path]=/docs" >/dev/null 2>&1; then
    echo "  Pages enabled."
  elif gh api -X PUT "repos/${SLUG}/pages" \
       -f "source[branch]=${BRANCH}" -f "source[path]=/docs" >/dev/null 2>&1; then
    echo "  Pages updated."
  else
    warn "  Could not enable Pages automatically (private repo? Pages already configured?)."
    warn "  Do it by hand: Settings -> Pages -> Source: Deploy from a branch -> ${BRANCH} -> /docs"
  fi

  info "Letting the refresh Action push commits (so the site updates itself)..."
  gh api -X PUT "repos/${SLUG}/actions/permissions/workflow" \
    -f default_workflow_permissions=write -F can_approve_pull_request_reviews=false >/dev/null 2>&1 \
    && echo "  Workflow permissions set to read/write." \
    || warn "  Set it by hand: Settings -> Actions -> General -> Workflow permissions -> Read and write."
fi

# ---------- 7. say what happened ----------
echo
info "Pushed to: https://github.com/${SLUG}"
echo "Website    : ${PAGES_URL}   (first build takes 1-3 minutes)"
echo
echo "If the URL 404s after 3 minutes:"
echo "  1. Settings -> Pages -> Source: Deploy from a branch -> ${BRANCH} -> /docs -> Save"
echo "  2. Settings -> Actions -> General -> Workflow permissions -> Read and write -> Save"
echo "  3. Actions tab -> 'Refresh snapshot' -> Run workflow  (populates the latest numbers)"
