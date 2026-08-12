#!/bin/bash
# One-time server setup for the News Bias Analyzer. Run as root (sudo).
# Idempotent — safe to re-run. Touches ONLY: docker install (incl. moving the
# stale 2019 /var/lib/docker aside and writing /etc/docker/daemon.json),
# /srv/news_bias, /backup/news_bias, and the news-bias-backup systemd units.

set -euo pipefail

echo "== 1/4 Docker =="
# The docker group vanished with the purged 2019 install; docker.socket
# (SocketGroup=docker) cannot start without it — this broke the first run of
# this script mid-install. Create it before anything touches the service.
getent group docker >/dev/null || groupadd --system docker
# Heal any half-configured packages from that interrupted run (no-op otherwise).
dpkg --configure -a
# The 2019 install also left this same repo in sources.list; comment it out so
# apt stops warning about the duplicate (docker.list is the maintained entry).
sed -i 's|^deb \[arch=amd64\] https://download.docker.com/linux/ubuntu bionic stable$|# superseded by sources.list.d/docker.list: &|' /etc/apt/sources.list

if ! command -v docker >/dev/null; then
  # A 2019 docker-ce install left images/containers/swarm state in
  # /var/lib/docker; a new engine would adopt and try to resume it. Park it
  # instead of deleting — reclaim space later with: rm -rf /var/lib/docker.old-2019
  if [ -d /var/lib/docker ] && [ ! -d /var/lib/docker.old-2019 ]; then
    mv /var/lib/docker /var/lib/docker.old-2019
  fi
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
# Cap container log growth — this box runs unattended for years at a time.
FRESH_DAEMON_JSON=0
if [ ! -f /etc/docker/daemon.json ]; then
  mkdir -p /etc/docker
  cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF
  FRESH_DAEMON_JSON=1
fi
systemctl enable --now docker
# If dpkg's postinst already started docker before we wrote daemon.json,
# a restart is needed for it to take effect (only on the run that wrote it).
[ "$FRESH_DAEMON_JSON" = "1" ] && systemctl restart docker
usermod -aG docker adminer
echo "adminer added to docker group (takes effect on next login)"

echo "== 2/4 Directories =="
mkdir -p /srv/news_bias/pgdata /srv/news_bias/backups /srv/news_bias/logs /srv/news_bias/batches
mkdir -p /backup/news_bias
# Marker proving the external drive is really mounted — backup.sh refuses to
# write a "backup" onto the root disk without it.
touch /backup/news_bias/.backup-drive-marker
# Deliberately not recursive on pgdata: once Postgres initializes it, the
# files belong to the postgres container user and must stay that way.
chown adminer:adminer /srv/news_bias /srv/news_bias/backups /srv/news_bias/logs /srv/news_bias/batches
[ -z "$(ls -A /srv/news_bias/pgdata 2>/dev/null)" ] && chown adminer:adminer /srv/news_bias/pgdata
chown -R adminer:adminer /backup/news_bias
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
