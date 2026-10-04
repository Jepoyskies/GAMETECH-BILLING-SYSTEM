#!/bin/bash
echo "=== 1. IS auto-suspend IN THE BEAT SCHEDULE? ==="
sed -n '250,300p' /root/GAMETECH-BILLING-SYSTEM/gametech_core/settings.py | grep -nE '"task"|crontab|CELERY_BEAT' 
echo
echo "  searching whole settings for auto_suspend:"
grep -n "auto_suspend" /root/GAMETECH-BILLING-SYSTEM/gametech_core/settings.py || echo "    NOT PRESENT in settings.py"
echo
echo "=== 2. MANUAL AUTO-SUSPEND PAGE ==="
grep -n "auto-suspend" /root/GAMETECH-BILLING-SYSTEM/billing/urls.py
echo
echo "=== 3. DOES THE 'Connected, Unpaid' QUEUE EXIST? ==="
grep -rn "Connected, Unpaid\|connected_unpaid\|connected-unpaid" /root/GAMETECH-BILLING-SYSTEM/billing --include=*.py --include=*.html | head -8
echo
echo "=== 4. CUSTOMER LIST FILTERS AVAILABLE ==="
grep -rnoE 'name="[a-z_]*filter[a-z_]*"|value="(expired|active|suspended|pending|pull out|closed_not_installed)"' /root/GAMETECH-BILLING-SYSTEM/billing/templates/billing/customer_list.html 2>/dev/null | head -12
echo
echo "=== 5. IS THERE A CONNECTION-STATE / OUTAGE FILTER? ==="
grep -rnoE 'outage|is_connected|unpaid' /root/GAMETECH-BILLING-SYSTEM/billing/templates/billing/customer_list.html | head -10