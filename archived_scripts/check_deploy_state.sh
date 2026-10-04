#!/bin/bash
cd /root/GAMETECH-BILLING-SYSTEM
echo "=== HEAD ==="
git log --oneline -3
echo
echo "=== does the running container have the fix? ==="
docker exec gametech-web grep -c 'job_type' /app/dispatch/views.py || echo "0 occurrences"
echo
echo "=== the real lines ==="
docker exec gametech-web grep -n 'ticket_type\|job_type\|type_option' /app/dispatch/views.py | head -8
echo
echo "=== git status ==="
git status --short | head -5