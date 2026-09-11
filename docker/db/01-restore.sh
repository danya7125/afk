#!/bin/bash
set -e

echo "Restoring mfc_data.dump..."

pg_restore \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --no-owner \
  --no-privileges \
  /docker-entrypoint-initdb.d/mfc_data.dump

echo "Database restore completed."