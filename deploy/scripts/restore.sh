#!/usr/bin/env bash
# Restore: sudo ./scripts/restore.sh backups/mongo-XXXX.archive.gz [backups/uploads-XXXX.tar.gz]
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then exec sudo bash "$0" "$@"; fi
cd "$(dirname "$0")/.."
source .env
ARCHIVE=${1:?Sebutkan file backup mongo (.archive.gz)}
UPLOADS=${2:-}
read -r -p "Data database $DB_NAME akan DITIMPA. Ketik YA untuk lanjut: " OK
[ "$OK" = "YA" ] || { echo "Dibatalkan."; exit 1; }
docker compose exec -T mongo mongorestore --quiet --drop \
  --username "$MONGO_ROOT_USER" --password "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin \
  --nsInclude "$DB_NAME.*" --archive="/backups/$(basename "$ARCHIVE")" --gzip
if [ -n "$UPLOADS" ]; then
  tar -xzf "$UPLOADS" -C data
fi
docker compose restart backend
echo "Restore selesai."
