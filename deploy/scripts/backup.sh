#!/usr/bin/env bash
# Backup MongoDB + file upload RelayLab OMS. Jalankan dari folder deploy/.
set -euo pipefail
cd "$(dirname "$0")/.."
source .env
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p backups
docker compose exec -T mongo mongodump --quiet \
  --username "$MONGO_ROOT_USER" --password "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin \
  --db "$DB_NAME" --archive=/backups/mongo-$STAMP.archive.gz --gzip
tar -czf backups/uploads-$STAMP.tar.gz -C data uploads
find backups -maxdepth 1 -type f -mtime +30 -delete
echo "Backup selesai: backups/mongo-$STAMP.archive.gz dan backups/uploads-$STAMP.tar.gz"
