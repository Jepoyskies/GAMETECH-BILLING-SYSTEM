#!/bin/bash
echo "=== full traceback(s) from the last 30m ==="
docker logs --since 30m gametech-web 2>&1 | grep -A40 "Traceback" | head -80