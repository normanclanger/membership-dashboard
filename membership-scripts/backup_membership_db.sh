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
