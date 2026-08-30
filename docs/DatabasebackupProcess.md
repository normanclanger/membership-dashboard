# Membership Dashboard — Database Backup System

**Created:** 29 August 2026
**Purpose:** Automated daily backups of the Supabase PostgreSQL membership database, with 30-day local retention and a tested restore procedure.

---

## 1. Backup destination

Backups are stored on the Raspberry Pi in:

```text
/home/tim/membership-backups/
```

Backup filenames use the format:

```text
membership_YYYY-MM-DD_HHMMSS.dump
```

For example:

```text
membership_2026-08-29_082537.dump
```

The backups use PostgreSQL's **custom dump format**, which is suitable for restoration with `pg_restore`.

---

## 2. Supabase connection details

The database connection string is stored separately from the backup script in:

```text
/home/tim/.membership-dashboard/supabase.env
```

The file contains the `DATABASE_URL` environment variable.

The backup script explicitly loads this file rather than relying on the variable already being present in the shell environment.

The script also checks that:

1. The environment file exists.
2. `DATABASE_URL` is populated.

This prevents an accidental attempt to connect to the Pi's local PostgreSQL database.

---

## 3. Backup script

The script is:

```text
/home/tim/membership-dashboard/membership-scripts/backup_membership_db.sh
```

Final version:

```bash
#!/bin/bash

set -e

# Load Supabase database connection details
ENV_FILE="$HOME/.membership-dashboard/supabase.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: Supabase environment file not found: $ENV_FILE"
    exit 1
fi

source "$ENV_FILE"

if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL is not set."
    exit 1
fi

BACKUP_DIR="$HOME/membership-backups"
DATE=$(date +"%Y-%m-%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/membership_$DATE.dump"

mkdir -p "$BACKUP_DIR"

echo "Starting database backup..."
echo "Destination: $BACKUP_FILE"

# PostgreSQL 17 client
/usr/lib/postgresql/17/bin/pg_dump \
    "$DATABASE_URL" \
    --format=custom \
    --file="$BACKUP_FILE"

echo "Backup completed successfully:"
ls -lh "$BACKUP_FILE"

# Remove backups older than 30 days
echo "Removing backups older than 30 days..."

find "$BACKUP_DIR" \
    -type f \
    -name "membership_*.dump" \
    -mtime +30 \
    -delete

echo "Backup maintenance completed."
```

---

## 4. PostgreSQL client versions

Initially, the Pi was using PostgreSQL 15 tools:

```text
pg_restore (PostgreSQL) 15.19
pg_dump (PostgreSQL) 15.19
```

The Supabase dump was produced using a newer PostgreSQL format and PostgreSQL 15 `pg_restore` reported:

```text
pg_restore: error: unsupported version (1.16) in file header
```

PostgreSQL 17 tools were therefore installed/used.

The PostgreSQL 17 binaries are located at:

```text
/usr/lib/postgresql/17/bin/
```

The backup script explicitly uses:

```text
/usr/lib/postgresql/17/bin/pg_dump
```

and the successful restore test used:

```text
/usr/lib/postgresql/17/bin/pg_restore
```

---

## 5. Important distinction: Supabase vs local PostgreSQL

We verified that:

```bash
psql "$DATABASE_URL"
```

connects to the **Supabase database**, because `DATABASE_URL` points to Supabase.

It does not use the Pi's local PostgreSQL database.

The Pi's local PostgreSQL installation was used only for testing the restoration.

---

## 6. Restore test

To prove that the backups were actually usable, a fresh local PostgreSQL database was created:

```text
membership_restore_test
```

The backup was restored into it using:

```bash
sudo -u postgres /usr/lib/postgresql/17/bin/pg_restore \
    --dbname=membership_restore_test \
    --no-owner \
    --no-acl \
    "/tmp/membership_2026-08-28_220339.dump"
```

There were four warnings/errors relating to Supabase-specific infrastructure:

* `transaction_timeout`
* `supabase_vault`
* `vault.secrets`
* related Vault infrastructure

These did **not** prevent restoration of the application's public tables.

The restored database contained all ten application tables.

---

## 7. Restore verification

The restored database was checked with:

```bash
sudo -u postgres psql -d membership_restore_test -c "\dt public.*"
```

It contained:

```text
districts
full_member_types
members
membership_classes
membership_statuses
payment_import_items
payment_import_lines
payment_imports
payments
towers
```

The row counts were then compared with the live Supabase database.

Expected and restored counts matched:

```text
districts                    4
full_member_types            5
members                    790
membership_classes           3
membership_statuses          3
payment_import_items         0
payment_import_lines         0
payment_imports              0
payments                  1338
towers                     139
```

An actual member record was also queried from the restored database to confirm that the data itself, rather than merely the table structure/counts, had been restored correctly.

This established that the backup could successfully be restored.

---

## 8. Local restore databases

During testing two local databases existed:

```text
membership_backup
membership_restore_test
```

`membership_restore_test` was subsequently deleted because it had served its purpose.

The remaining:

```text
membership_backup
```

was retained as a local restored copy/test database.

---

## 9. 30-day retention

The backup script automatically removes backup files older than 30 days:

```bash
find "$BACKUP_DIR" \
    -type f \
    -name "membership_*.dump" \
    -mtime +30 \
    -delete
```

Only files matching:

```text
membership_*.dump
```

are affected.

This means unrelated files in the backup directory are not removed.

---

## 10. systemd service

Automation uses systemd rather than cron.

The service is:

```text
/etc/systemd/system/membership-backup.service
```

Contents:

```ini
[Unit]
Description=Membership database backup

[Service]
Type=oneshot
User=tim
ExecStart=/home/tim/membership-dashboard/membership-scripts/backup_membership_db.sh
```

The service runs the existing, already-tested backup script.

It runs as user:

```text
tim
```

---

## 11. systemd timer

The timer is:

```text
/etc/systemd/system/membership-backup.timer
```

Contents:

```ini
[Unit]
Description=Daily membership database backup

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

The backup therefore runs automatically every day at:

```text
02:00
```

`Persistent=true` means that if the Raspberry Pi is powered off when the scheduled time occurs, systemd can run the missed timer after the Pi comes back online.

---

## 12. Enabling the timer

After creating the service and timer, systemd was reloaded:

```bash
sudo systemctl daemon-reload
```

The timer was enabled and started:

```bash
sudo systemctl enable --now membership-backup.timer
```

Its status showed:

```text
Loaded: loaded
Active: active (waiting)
Trigger: Sun 2026-08-30 02:00:00 BST
```

The timer was therefore confirmed to be active.

---

## 13. Automation test

We did not simply leave the timer to run overnight.

The actual systemd service was manually triggered:

```bash
sudo systemctl start membership-backup.service
```

The service completed with:

```text
code=exited, status=0/SUCCESS
```

The systemd log confirmed:

```text
Starting database backup...
Destination: /home/tim/membership-backups/membership_2026-08-29_082537.dump
Backup completed successfully
Removing backups older than 30 days...
Backup maintenance completed.
```

The new `.dump` file was also confirmed in:

```text
~/membership-backups/
```

This proved that systemd can successfully execute the backup script.

---

## 14. Useful maintenance commands

### Check the next scheduled backup

```bash
systemctl list-timers membership-backup.timer
```

### Check timer status

```bash
systemctl status membership-backup.timer
```

### Check the most recent service run

```bash
systemctl status membership-backup.service
```

### View backup history/logs

```bash
journalctl -u membership-backup.service
```

### List available backup files

```bash
ls -lh ~/membership-backups/
```

### Manually run a backup

```bash
~/membership-scripts/backup_membership_db.sh
```

### Manually trigger through systemd

```bash
sudo systemctl start membership-backup.service
```

---

# Final configuration

```text
Supabase PostgreSQL
        │
        │ DATABASE_URL
        ▼
~/.membership-dashboard/supabase.env
        │
        ▼
backup_membership_db.sh
        │
        │ PostgreSQL 17 pg_dump
        ▼
~/membership-backups/
        │
        ├── membership_YYYY-MM-DD_HHMMSS.dump
        │
        └── files older than 30 days automatically removed


systemd timer
        │
        │ Every day at 02:00
        ▼
membership-backup.service
        │
        ▼
backup_membership_db.sh
```

## Status

**Backup system: COMPLETE AND TESTED**

The following have all been successfully verified:

* Supabase connection
* `DATABASE_URL` loading
* PostgreSQL 17 `pg_dump`
* Custom-format dump creation
* Local `pg_restore`
* Restoration into a fresh database
* Restoration of all application tables
* Matching row counts
* Actual restored member data
* 30-day retention
* systemd service execution
* systemd timer activation
* Scheduled daily execution
