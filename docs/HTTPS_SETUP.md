# Gametech Unli Fiber — Production HTTPS & Domain Transition Runbook

This runbook documents the exact, production-ready steps to activate custom domain routing, automated SSL certificate issuance (Certbot / Let's Encrypt), Nginx HTTPS reverse proxying, and Django security hardening once the domain (e.g. `gametech.com.ph` or `gametechunlifiber.com`) is purchased.

> **CRITICAL PRODUCTION GUARD:**  
> Do **NOT** enable SSL redirect or HTTPS cookies before obtaining and verifying a valid SSL certificate. Enabling them prematurely while accessing via raw IP will lock out staff and portal subscribers with `SSL_ERROR_RX_RECORD_TOO_LONG` or CSRF cookie rejection.

---

## Architecture Overview

```
                      [ Client Browser / Mobile ]
                                  │
                                  ▼
                         Cloudflare / DNS
                     (A Record -> 143.198.207.144)
                                  │
                       Port 80    ▼    Port 443
                     ┌───────────────────────────┐
                     │   Host Nginx Reverse Proxy │
                     │   (Certbot Let's Encrypt) │
                     └─────────────┬─────────────┘
                                   │ HTTP (Proxy Pass)
                                   ▼
                     ┌───────────────────────────┐
                     │ Docker Container (Web)    │
                     │ Gunicorn on Port 8000     │
                     └───────────────────────────┘
```

---

## Step 1: DNS Configuration at Domain Registrar

Log in to your domain registrar (e.g., GoDaddy, Namecheap, Cloudflare, DotPH) and configure DNS `A` records pointing to the DigitalOcean Droplet IPv4 address:

| Type | Host / Name | Value / Destination | TTL |
|---|---|---|---|
| **A** | `@` (root) | `143.198.207.144` | Auto / 300s |
| **A** | `www` | `143.198.207.144` | Auto / 300s |
| **A** | `portal` | `143.198.207.144` | Auto / 300s |

Verify DNS propagation from your terminal:
```bash
dig +short gametech.com.ph @1.1.1.1
# Expected output: 143.198.207.144
```

---

## Step 2: SSL Certificate Issuance via Certbot (Let's Encrypt)

On the DigitalOcean Droplet host shell (`ssh root@143.198.207.144`):

1. **Install Certbot and Nginx plugin:**
   ```bash
   apt update
   apt install -y certbot python3-certbot-nginx
   ```

2. **Temporarily stop host Nginx (or use webroot plugin):**
   ```bash
   certbot certonly --standalone -d gametech.com.ph -d www.gametech.com.ph -d portal.gametech.com.ph --email support@gametech.com.ph --agree-tos --no-eff-email
   ```

3. **Verify certificate generation:**
   Certificates will be saved to:
   - Certificate: `/etc/letsencrypt/live/gametech.com.ph/fullchain.pem`
   - Private Key: `/etc/letsencrypt/live/gametech.com.ph/privkey.pem`

4. **Verify automatic renewal timer:**
   ```bash
   systemctl status certbot.timer
   certbot renew --dry-run
   ```

---

## Step 3: Nginx Reverse Proxy Configuration

Update `/etc/nginx/sites-available/gametech` (or default site configuration):

```nginx
# HTTP - Redirect all traffic to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name gametech.com.ph www.gametech.com.ph portal.gametech.com.ph 143.198.207.144;

    # Allow ACME challenge for renewal
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS - Reverse Proxy to Docker Gunicorn container (Port 8000)
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name gametech.com.ph www.gametech.com.ph portal.gametech.com.ph;

    ssl_certificate /etc/letsencrypt/live/gametech.com.ph/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gametech.com.ph/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
        proxy_redirect off;
    }

    location /static/ {
        alias /root/GAMETECH-BILLING-SYSTEM/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    location /media/ {
        alias /root/GAMETECH-BILLING-SYSTEM/media/;
        expires 30d;
    }
}
```

Test and reload Nginx:
```bash
nginx -t
systemctl reload nginx
```

---

## Step 4: Django Environment Configuration (`.env`)

Once Nginx is active with HTTPS, update `/root/GAMETECH-BILLING-SYSTEM/.env` on the Droplet:

```env
# Domain & Hosts
ALLOWED_HOSTS=gametech.com.ph,www.gametech.com.ph,portal.gametech.com.ph,143.198.207.144,localhost,127.0.0.1

# CSRF Trusted Origins (must include https:// scheme)
CSRF_TRUSTED_ORIGINS=https://gametech.com.ph,https://www.gametech.com.ph,https://portal.gametech.com.ph,http://143.198.207.144

# Production HTTPS Flags (Set to True once SSL is operational)
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
```

---

## Step 5: Container Restart & Verification

1. **Restart web container to apply new settings:**
   ```bash
   ssh root@143.198.207.144 "docker restart gametech-billing-system-web-1"
   ```

2. **Verify headers and SSL response:**
   ```bash
   curl -I https://gametech.com.ph/login/
   ```
   Look for:
   - `HTTP/2 200`
   - `Strict-Transport-Security: max-age=31536000`
   - `Set-Cookie: ...; Secure; HttpOnly; SameSite=Lax`

---

## Emergency Rollback

If HTTPS fails or SSL cert expires unexpectedly:
1. Edit `/root/GAMETECH-BILLING-SYSTEM/.env` and set:
   ```env
   SESSION_COOKIE_SECURE=False
   CSRF_COOKIE_SECURE=False
   SECURE_SSL_REDIRECT=False
   ```
2. Restart container:
   ```bash
   docker restart gametech-billing-system-web-1
   ```
3. Direct access via `http://143.198.207.144/login/` will immediately resume functioning.
