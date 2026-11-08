# Runbook: Backup & Restore

## Taegliches Backup (Cron, 02:30 Uhr)

    # DB-Dump
    docker compose exec -T db pg_dump -U plm plm | gzip \
      > backups/plm-$(date +%F).sql.gz

    # Uploads/Originale synchronisieren
    rsync -a --delete uploads/ backup-target:plm-uploads/

## Pruefung

- Restore-Test monatlich in eine scratch-DB.
- Backupgroesse monitoren (Wachstum = Dateivolumen im Blick behalten).

## Restore

    docker compose down api
    gunzip -c backups/plm-2026-11-08.sql.gz \
      | docker compose exec -T db psql -U plm -d plm
    rsync -a backup-target:plm-uploads/ uploads/
    docker compose up -d api
    # Verifikation: /health, danach Stichprobenartikel + Audit-Log pruefen
