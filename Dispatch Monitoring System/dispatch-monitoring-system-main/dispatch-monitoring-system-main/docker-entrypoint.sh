#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" 2>/dev/null; do
  sleep 2
done
echo "PostgreSQL is ready."

# FIRS-TIME SETUP ONLY
# echo "Applying database migrations..."
# cd /app/backend && npx prisma migrate deploy

# echo "Seeding config options..."
# node /app/backend/dist/prisma/seedConfigOptions.js

# echo "Seeding admin account..."
# node /app/backend/dist/prisma/seedSuperAdmin.js

echo "Starting application..."
exec node /app/backend/dist/src/index.js
