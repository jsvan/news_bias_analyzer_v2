#!/bin/bash
# Daily snapshot refresh for the public GitHub Pages dashboard.
# Exports static JSON from the database, syncs it into frontend/public/snapshots,
# and commits + pushes ONLY that path; the Pages workflow deploys it (~1-2 min).
# Run via cron as adminer (09:00 local — the 05:00 scrape's batches normally
# finish collecting by ~06:15, so the site stays a few hours behind at most).
#
# This checkout is SHARED (Julian / the Mac agent work in it directly), so the
# git steps are deliberately paranoid: bail out of the commit+push if anything
# is staged or a rebase/merge is in progress, and never `git add` more than the
# snapshots path.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
BATCHES_DIR="${BATCHES_DIR:-/srv/news_bias/batches}"
TMP_DIR="$BATCHES_DIR/.snapshot_export_tmp"
SNAP_DIR="$APP_DIR/frontend/public/snapshots"
ENTITIES="${SNAPSHOT_ENTITIES:-200}"

# One export at a time; a stuck previous run must not stack.
exec 9>/srv/news_bias/.snapshot_export.lock
flock -n 9 || { echo "[export] another export is running; exiting"; exit 0; }

echo "[export] $(date -Is) exporting snapshots (--entities $ENTITIES)"
# tail: keep the exporter's closing summary, not its per-entity INFO chatter
# (pipefail still surfaces a failed export through the pipe).
docker compose -f "$SCRIPT_DIR/docker-compose.yml" run --rm -T --no-deps scheduler \
  python -m server.export_snapshots --entities "$ENTITIES" --out /app/batches/.snapshot_export_tmp \
  2>&1 | tail -n 25

# A failed/empty export must never rsync --delete the good snapshots away.
if [ ! -s "$TMP_DIR/meta.json" ] || [ "$(ls "$TMP_DIR/entity" 2>/dev/null | wc -l)" -lt 100 ]; then
  echo "[export] ERROR: export looks empty/truncated ($TMP_DIR); refusing to sync" >&2
  exit 1
fi

cd "$APP_DIR"

# Shared-checkout guards: leave someone's in-progress work strictly alone.
# These are expected conditions, not failures — skip today, retry tomorrow.
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ] || [ -f .git/MERGE_HEAD ]; then
  echo "[export] rebase/merge in progress in $APP_DIR; skipping git steps today"
  exit 0
fi
if ! git diff --cached --quiet; then
  echo "[export] index has staged changes (concurrent work); skipping git steps today"
  exit 0
fi

# Integrate remote work before we dirty the tree — but git refuses to rebase
# over ANY unstaged change, so only pull when the tree is clean outside the
# snapshots path. When someone's mid-edit we skip the pull (never autostash
# under a live editor) and still commit/push just the snapshots; if origin
# moved meanwhile the push is rejected and tomorrow's clean run rebases the
# leftover commit on top and pushes both.
if git status --porcelain -- . ':(exclude)frontend/public/snapshots' | grep -q .; then
  echo "[export] working tree has concurrent edits; skipping pull, committing snapshots only"
else
  git pull --rebase --quiet origin master
fi

rsync -a --delete "$TMP_DIR/" "$SNAP_DIR/"

git add frontend/public/snapshots
if git diff --cached --quiet; then
  echo "[export] no snapshot changes; nothing to push"
  exit 0
fi
git commit --quiet -m "Refresh snapshots (automated daily export)"
if git push --quiet origin master; then
  echo "[export] done: pushed $(git rev-parse --short HEAD)"
else
  echo "[export] push rejected (origin moved during concurrent work?); commit kept, tomorrow's run will rebase+push"
fi
