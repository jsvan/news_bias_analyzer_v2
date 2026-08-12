#!/bin/bash
# One-time server setup for the News Bias Analyzer. Run as root (sudo).
# Idempotent — safe to re-run. Touches ONLY: docker install, /srv/news_bias,
# /backup/news_bias, and the news-bias-backup systemd units.

set -euo pipefail

echo "== 1/4 Docker =="
if ! command -v docker >/dev/null; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu bionic stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
else
  echo "docker already installed: $(docker --version)"
  # Ensure compose v2 plugin is present even if docker predates this script
  docker compose version >/dev/null 2>&1 || apt-get install -y docker-compose-plugin
fi
systemctl enable --now docker
usermod -aG docker adminer
echo "adminer added to docker group (takes effect on next login)"

echo "== 2/4 Directories =="
mkdir -p /srv/news_bias/pgdata /srv/news_bias/backups /srv/news_bias/logs /srv/news_bias/batches
mkdir -p /backup/news_bias
# Marker proving the external drive is really mounted — backup.sh refuses to
# write a "backup" onto the root disk without it.
touch /backup/news_bias/.backup-drive-marker
chown -R adminer:adminer /srv/news_bias /backup/news_bias
echo "created /srv/news_bias/* and /backup/news_bias (owner adminer)"

echo "== 3/4 Backup timer =="
if [ -f /tmp/news-bias-backup.service ] && [ -f /tmp/news-bias-backup.timer ]; then
  cp /tmp/news-bias-backup.service /tmp/news-bias-backup.timer /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now news-bias-backup.timer
  echo "nightly backup timer enabled (04:30)"
else
  echo "WARNING: unit files not found in /tmp — copy them and re-run this script"
fi

echo "== 4/4 Summary =="
docker --version
docker compose version
systemctl list-timers news-bias-backup.timer --no-pager || true
echo "Setup complete. Next: rsync the app to /srv/news_bias/app (as adminer, no sudo needed)."
