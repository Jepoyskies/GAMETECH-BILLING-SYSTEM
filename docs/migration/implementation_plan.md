# Production Cleanup & Docker Optimization Plan

Since we are launching this live on Digital Ocean using Docker, we must ensure the application is secure, performant, and free of unnecessary bloat.

## User Review Required

> [!IMPORTANT]
> This plan includes deleting a significant amount of old/legacy files. Please review the **Proposed Deletions** carefully to ensure you do not need them anymore. If you still need any of these, let me know!

> [!WARNING]
> We will be changing the web server from the Django development server (`runserver`) to `Gunicorn`. This is required for production as `runserver` cannot handle multiple concurrent users securely and efficiently. We will also introduce `whitenoise` to serve your static files securely.

## Open Questions
- Do you have a specific domain name or IP address you'd like to restrict `ALLOWED_HOSTS` to, or should we keep it as `['*']` for now so it works on any Digital Ocean Droplet IP?

## Proposed Changes

---

### Remove Legacy & Scratch Files

We will permanently delete the following files and directories as they are not needed for the Python/Django production deployment.

- `isp/` directory (Legacy PHP Codebase)
- `_legacy_archive/` directory (Old PHP backups)
- `scratch_original_dashboard.html`
- `billing_views_funcs.txt`
- `ts_login.txt`
- `ZeroTier.msi` (Installer files should not be in source control)
- `Dockerfile.bak` and `docker-compose.yml.bak`

---

### Django Production Settings

#### [MODIFY] [settings.py](file:///c:/Users/gametech/Documents/GAMETECH-BILLING-SYSTEM/gametech_core/settings.py)
- Change `DEBUG = True` to use environment variables (`env('DEBUG', default=False)`), defaulting to `False` for production security.
- Add `STATIC_ROOT = BASE_DIR / 'staticfiles'` for Docker static file collection.
- Add `whitenoise.middleware.WhiteNoiseMiddleware` to `MIDDLEWARE` to efficiently serve static assets (CSS, JS, images) directly from the Django Docker container.

---

### Docker & Production Server Optimization

#### [MODIFY] [requirements.txt](file:///c:/Users/gametech/Documents/GAMETECH-BILLING-SYSTEM/requirements.txt)
- Add `gunicorn` (Production Python Web Server).
- Add `whitenoise` (Production Static Files handler).

#### [MODIFY] [start_web.sh](file:///c:/Users/gametech/Documents/GAMETECH-BILLING-SYSTEM/docker/start_web.sh)
- Add `python manage.py collectstatic --noinput` to prepare static assets on boot.
- Replace the development server command (`python manage.py runserver`) with the production-ready server command (`gunicorn gametech_core.wsgi:application --bind 0.0.0.0:8000`).

---

## Verification Plan

### Automated Tests
- Build and verify the Docker configuration locally or manually confirm that all syntax is correct before deployment.

### Manual Verification
- We will deploy/run the updated Docker composition and confirm that the site loads correctly, static files are served, and old legacy files are completely wiped.
