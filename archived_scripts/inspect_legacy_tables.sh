#!/bin/bash
F=/root/backups/backup-2026-03-20_06-21-43.sql

echo "=== customers TABLE DEFINITION ==="
sed -n "/CREATE TABLE \`customers\`/,/^) ENGINE/p" "$F" | sed 's/,$//' | head -60

echo
echo "=== payments TABLE DEFINITION (expiry fields) ==="
sed -n "/CREATE TABLE \`payments\`/,/^) ENGINE/p" "$F" | sed 's/,$//' | head -40