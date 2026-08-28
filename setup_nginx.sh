#!/bin/bash
cat << 'EOF' > /etc/nginx/sites-available/gametech
server {
    listen 80;
    server_name 143.198.207.144;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/gametech /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
systemctl restart nginx
cd /root/GAMETECH-BILLING-SYSTEM && docker-compose restart web
