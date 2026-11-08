# Runbook: Backup & Restore

## Daily backup (cron, 02:30)

    # DB dump
    docker compose exec -T db pg_dump -U plm plm | gzip \
      > backups/plm-$(date +%F).sql.gz

    # sync uploads/originals
    rsync -a --delete uploads/ backup-target:plm-uploads/

## Verification

- Restore test monthly into a scratch DB.
- Monitor backup size (growth = keep an eye on file volume).

## Restore

    docker compose down api
    gunzip -c backups/plm-2026-11-08.sql.gz \
      | docker compose exec -T db psql -U plm -d plm
    rsync -a backup-target:plm-uploads/ uploads/
    docker compose up -d api
    # verify: /health, then spot-check parts + audit log
