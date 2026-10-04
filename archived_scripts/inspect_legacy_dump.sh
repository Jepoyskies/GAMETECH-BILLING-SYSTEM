#!/bin/bash
# What does the legacy dump actually contain? Specifically: does it carry an
# expiry / due date per subscriber? That decides whether the import can
# preserve "28 days remaining" or has to invent it.
F=/root/backups/backup-2026-03-20_06-21-43.sql

echo "=== SIZE / TYPE ==="
ls -la "$F"
head -c 100 "$F" | tr -d '\0'
echo

echo
echo "=== TABLES ==="
grep -oiE 'CREATE TABLE [^ (]+' "$F" | sed 's/CREATE TABLE //I' | tr -d '`"(' | sort -u

echo
echo "=== EXPIRY-LIKE COLUMNS (and which table) ==="
grep -oiE '`[a-z_]*(expir|due|end_date|next_pay|billing_cycle|paid_until)[a-z_]*`' "$F" \
  | tr -d '`' | tr 'A-Z' 'a-z' | sort | uniq -c | sort -rn

echo
echo "=== SAMPLE: the customer-ish table columns ==="
for t in customers client customers_info subscribers; do
  if grep -qiE "CREATE TABLE \`?$t" "$F"; then
    echo "--- $t ---"
    awk "/CREATE TABLE \`?$t\`? *\(/,/^\) *ENGINE/" "$F" | grep -oiE '^\s*\`[a-z_]+\`' | tr -d '`' | tr '\n' ' '
    echo
  fi
done