#!/bin/bash
# Nightly backup for the news_bias database.
# Dumps (custom format), verifies the dump is readable, rotates old backups,
# and optionally uploads offsite via rclone. Run via systemd timer (see systemd/).
#
# Exit nonzero on any failure so systemd marks the run failed (visible in
# `systemctl status news-bias-backup` / journalctl).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load server config
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a; source "$SCRIPT_DIR/.env"; set +a
fi

BACKUP_DIR="${BACKUP_DIR:-/srv/news_bias/backups}"
KEEP_DAILY="${KEEP_DAILY:-14}"
KEEP_WEEKLY="${KEEP_WEEKLY:-8}"
RCLONE_REMOTE="${RCLONE_REMOTE:-}"
DB_NAME="news_bias"
DB_USER="postgres"

mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/daily/${DB_NAME}_${STAMP}.dump"

echo "[backup] dumping $DB_NAME -> $OUT"
docker compose -f "$SCRIPT_DIR/docker-compose.yml" exec -T postgres \
  pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$OUT"

# Verify: a dump we can't list is not a backup. Implicit stdin, NOT a named
# /dev/stdin — pg_restore treats a named file as seekable, and the docker-exec
# pipe isn't ("did not find magic string" failure).
docker compose -f "$SCRIPT_DIR/docker-compose.yml" exec -T postgres \
  pg_restore --list < "$OUT" > /dev/null
SIZE=$(du -h "$OUT" | cut -f1)
echo "[backup] verified readable ($SIZE)"

# Warn loudly if the dump shrank >20% vs the previous one — catches a
# silently-emptied database before rotation destroys the last good copy.
PREV=$(ls -1t "$BACKUP_DIR/daily/"*.dump 2>/dev/null | sed -n 2p || true)
if [ -n "$PREV" ]; then
  PREV_BYTES=$(stat -c%s "$PREV" 2>/dev/null || stat -f%z "$PREV")
  NEW_BYTES=$(stat -c%s "$OUT" 2>/dev/null || stat -f%z "$OUT")
  if [ "$NEW_BYTES" -lt $((PREV_BYTES * 80 / 100)) ]; then
    echo "[backup] WARNING: new dump ($NEW_BYTES bytes) is >20% smaller than previous ($PREV_BYTES bytes)." >&2
    echo "[backup] WARNING: check the database before assuming this backup is good." >&2
  fi
fi

# Sunday: keep a weekly copy on a longer retention schedule.
if [ "$(date +%u)" = "7" ]; then
  cp "$OUT" "$BACKUP_DIR/weekly/"
  echo "[backup] weekly copy kept"
fi

# Rotate. -mtime is deliberate (age-based), not count-based: a burst of manual
# dumps can't push the old nightly copies out early.
find "$BACKUP_DIR/daily"  -name '*.dump' -mtime +"$KEEP_DAILY" -delete
find "$BACKUP_DIR/weekly" -name '*.dump' -mtime +$((KEEP_WEEKLY * 7)) -delete

# Second-drive copy: mirror to the external backup drive.
# The marker file proves the real drive is mounted — without this check, an
# unmounted /mnt/backup is just an empty directory on the root disk, and the
# "backup" would silently go to the machine it's meant to protect against.
# One-time setup after mounting the drive: touch "$OFFSITE_DIR/.backup-drive-marker"
OFFSITE_DIR="${OFFSITE_DIR:-}"
if [ -n "$OFFSITE_DIR" ]; then
  if [ -f "$OFFSITE_DIR/.backup-drive-marker" ]; then
    mkdir -p "$OFFSITE_DIR/daily"
    cp "$OUT" "$OFFSITE_DIR/daily/"
    find "$OFFSITE_DIR/daily" -name '*.dump' -mtime +$((KEEP_WEEKLY * 7)) -delete
    echo "[backup] copied to external drive: $OFFSITE_DIR/daily/"
  else
    echo "[backup] ERROR: no marker file at $OFFSITE_DIR/.backup-drive-marker — drive unmounted?" >&2
    echo "[backup] (after mounting the drive once, run: touch $OFFSITE_DIR/.backup-drive-marker)" >&2
    exit 1
  fi
fi

# Optional cloud copy on top. A drive plugged into the same machine survives a
# disk failure, but not fire/theft/surge — cloud is the belt to the drive's braces.
if [ -n "$RCLONE_REMOTE" ]; then
  echo "[backup] uploading to $RCLONE_REMOTE"
  rclone copy "$OUT" "$RCLONE_REMOTE/daily/"
  rclone delete --min-age "${KEEP_DAILY}d" "$RCLONE_REMOTE/daily/" || true
else
  echo "[backup] NOTE: RCLONE_REMOTE not set — no offsite copy exists."
fi

echo "[backup] done: $OUT"
