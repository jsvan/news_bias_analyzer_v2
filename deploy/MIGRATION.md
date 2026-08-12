# Migration to the home server (adminer@100.100.142.12)

Why this exists: in July 2026 the entire corpus (~221k articles) was lost when
Docker Desktop's VM on the Mac was recreated — the only copy of the data lived
inside Docker's own storage, with no backups. This setup fixes both mistakes:
data on a real host path (bind mount), and automated verified backups mirrored
to the external 1.8T drive at `/backup`.

Server facts (verified 2026-08-12): Ubuntu 18.04 x86_64 (EOL — see note at
bottom), no Docker preinstalled, Python 3.6.9 (too old → the app runs
containerized on python:3.12-slim, matching the Mac's venv), `/backup` is a
separate 1.8T ext4 drive, ports 5432/8000 free, `adminer` has sudo with
password.

DB facts: PostgreSQL 13.15 + TimescaleDB 2.15.3, zero hypertables in use →
dumps are plain-Postgres portable, no TimescaleDB restore ceremony.

## Layout

- `/srv/news_bias/app` — the code (rsynced from the Mac)
- `/srv/news_bias/pgdata` — Postgres data (bind-mounted into the container)
- `/srv/news_bias/backups` — nightly dumps (root disk)
- `/srv/news_bias/{logs,batches}` — app logs and OpenAI batch files
- `/backup/news_bias` — mirror of every dump on the external drive

Three containers via `deploy/docker-compose.yml`: `postgres`, `scheduler`
(scraper every 30 min + batch-analyzer daemon + stats jobs), `api` (port 8000).
`restart: unless-stopped` + the docker systemd service bring everything back on
reboot; no per-app systemd units. The only systemd pieces are the nightly
backup service + timer.

## Steps

1. **One sudo run** (installs Docker from Docker's official bionic repo, creates
   the layout, enables the backup timer):
   ```bash
   scp deploy/server_setup.sh deploy/systemd/news-bias-backup.* adminer@100.100.142.12:/tmp/
   ssh -t adminer@100.100.142.12 'sudo bash /tmp/server_setup.sh'
   ```
2. **Code**: `rsync -az --delete --exclude-from=deploy/rsync-exclude.txt ./ adminer@100.100.142.12:/srv/news_bias/app/`
3. **Secrets**: create `/srv/news_bias/app/deploy/.env` from `.env.example` —
   `POSTGRES_PASSWORD` (openssl rand -base64 24) and `OPENAI_API_KEY` (from the
   Mac's `.env`).
4. **Build + start**: `cd /srv/news_bias/app/deploy && docker compose up -d --build`
5. **Restore**: fresh dump from the Mac →
   `docker compose exec -T postgres pg_restore -U postgres -d news_bias --no-owner < dump`
   (duplicate `CREATE EXTENSION timescaledb` errors are harmless; missing
   relations are not).

## Verify (do not skip)

- [ ] `docker compose ps` — three services up, postgres healthy
- [ ] article count matches the Mac's at dump time; grows within the hour
      (scraper runs every 30 min)
- [ ] `docker compose logs scheduler --tail 50` — no tracebacks
- [ ] extension API answers: `curl http://100.100.142.12:8000/docs`
- [ ] **run a backup by hand and restore it into a throwaway DB** — a backup
      you have never restored is a hope, not a backup:
      ```bash
      sudo systemctl start news-bias-backup && journalctl -u news-bias-backup -n 20
      ls /backup/news_bias/daily/   # the external-drive mirror exists
      docker compose exec postgres createdb -U postgres restore_test
      docker compose exec -T postgres pg_restore -U postgres -d restore_test --no-owner \
        < "$(ls -t /srv/news_bias/backups/daily/*.dump | head -1)"
      docker compose exec postgres psql -U postgres -d restore_test -c "select count(*) from news_articles;"
      docker compose exec postgres dropdb -U postgres restore_test
      ```
- [ ] reboot test when convenient: `sudo reboot`, confirm all three containers
      return and the timer survives

## After migration

- Stop the Mac pipeline (scheduler/analyzer processes; `./run.sh docker down`
  — WITHOUT `-v`). Keep the Mac's final dump in `backups/` forever.
- Point the Chrome extension / dashboard at `http://100.100.142.12:8000`
  (or `home:8000` on Tailscale).
- Run the OpenAI batch recovery (199k requests) ON the server, where the data
  lands under nightly verified backups.

## Upgrading Postgres (do eventually — PG13 is past EOL)

Take a verified dump → point a second compose file at a pinned current image
(e.g. `timescale/timescaledb:2.x-pg17`) with a fresh empty `PGDATA_DIR` →
`pg_restore` → run the verify list → swap. Plain logical restore, because no
hypertables are in use. If hypertables are ever adopted, upgrades must instead
follow Timescale's `timescaledb_pre_restore()`/`timescaledb_post_restore()`
procedure with matching extension versions.

## Note on the host OS

Ubuntu 18.04 has been EOL since April 2023 — no security patches. Acceptable
for a Tailscale-internal family server, but worth an OS refresh eventually;
this deployment survives one untouched as long as `/srv/news_bias` and
`/backup` persist (that's the point of the bind mounts + external drive).
