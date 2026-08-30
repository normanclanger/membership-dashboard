#!/bin/bash

set -e

BACKUP_DIR="$HOME/membership-backups"
DATABASE_NAME="membership_backup"
PG_RESTORE="/usr/lib/postgresql/17/bin/pg_restore"

echo
echo "Membership Dashboard - Local Disaster Recovery"
echo "================================================"
echo

# Find the most recent backup
LATEST_BACKUP=$(find "$BACKUP_DIR" \
    -type f \
    -name "membership_*.dump" \
    -printf '%T@ %p\n' |
    sort -nr |
    head -1 |
    cut -d' ' -f2-)

if [ -z "$LATEST_BACKUP" ]; then
    echo "ERROR: No membership backup files found in:"
    echo "       $BACKUP_DIR"
    exit 1
fi

echo "Latest backup:"
echo "  $LATEST_BACKUP"
echo

ls -lh "$LATEST_BACKUP"
echo

read -r -p "This will REPLACE the local $DATABASE_NAME database. Continue? [y/N] " ANSWER

if [[ ! "$ANSWER" =~ ^[Yy]$ ]]; then
    echo
    echo "Restore cancelled."
    exit 0
fi

echo
echo "Stopping local connections to $DATABASE_NAME..."

sudo -u postgres psql -d postgres -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$DATABASE_NAME'
  AND pid <> pg_backend_pid();
"

set +e

echo "Dropping existing database..."

sudo -u postgres dropdb --if-exists "$DATABASE_NAME"

echo "Creating empty database..."

sudo -u postgres createdb "$DATABASE_NAME"

echo "Preparing backup for PostgreSQL restore..."

TEMP_BACKUP="/tmp/$(basename "$LATEST_BACKUP")"

cp "$LATEST_BACKUP" "$TEMP_BACKUP"
chmod 644 "$TEMP_BACKUP"

echo "Restoring backup..."

sudo -u postgres "$PG_RESTORE" \
    --dbname="$DATABASE_NAME" \
    --no-owner \
    --no-acl \
    "$TEMP_BACKUP"

rm -f "$TEMP_BACKUP"

set -e

echo "Granting local application read access..."

sudo -u postgres psql -d "$DATABASE_NAME" <<'SQL'
GRANT USAGE ON SCHEMA public TO membership_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO membership_app;
SQL

echo "Local application read access granted."

echo


echo
echo "Restore completed."
echo

echo "Checking restored tables..."

sudo -u postgres psql -d "$DATABASE_NAME" -c "
SELECT
    table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
"

echo
echo "Checking row counts..."

sudo -u postgres psql -d "$DATABASE_NAME" -c "
SELECT 'districts' AS table_name, count(*) FROM public.districts
UNION ALL
SELECT 'full_member_types', count(*) FROM public.full_member_types
UNION ALL
SELECT 'members', count(*) FROM public.members
UNION ALL
SELECT 'membership_classes', count(*) FROM public.membership_classes
UNION ALL
SELECT 'membership_statuses', count(*) FROM public.membership_statuses
UNION ALL
SELECT 'payment_import_items', count(*) FROM public.payment_import_items
UNION ALL
SELECT 'payment_import_lines', count(*) FROM public.payment_import_lines
UNION ALL
SELECT 'payment_imports', count(*) FROM public.payment_imports
UNION ALL
SELECT 'payments', count(*) FROM public.payments
UNION ALL
SELECT 'towers', count(*) FROM public.towers
ORDER BY table_name;
"

echo
echo "================================================"
echo "Local disaster-recovery restore completed."
echo "Database: $DATABASE_NAME"
echo "Backup:   $LATEST_BACKUP"
echo "================================================"
echo

echo
echo "Verifying restored database..."
echo

sudo -u postgres psql -d "$DATABASE_NAME" -c "
SELECT
    table_name,
    (
        xpath(
            '/row/count/text()',
            query_to_xml(
                format('SELECT count(*) FROM public.%I', table_name),
                false,
                true,
                ''
            )
        )
    )[1]::text::bigint AS count
FROM (
    VALUES
        ('districts'),
        ('full_member_types'),
        ('members'),
        ('membership_classes'),
        ('membership_statuses'),
        ('payment_import_items'),
        ('payment_import_lines'),
        ('payment_imports'),
        ('payments'),
        ('towers')
) AS t(table_name)
ORDER BY table_name;
"
