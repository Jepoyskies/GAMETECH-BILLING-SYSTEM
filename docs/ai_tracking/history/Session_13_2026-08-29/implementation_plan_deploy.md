# Digital Ocean Deployment Plan

Now that your local codebase is cleaned up and fully optimized for production, we will push these changes to GitHub and deploy them directly to your live Digital Ocean server.

## User Review Required

> [!WARNING]
> This will update the live production server. It will briefly restart the Docker containers on your droplet, which means the website will be down for about 30 seconds to a minute during the rebuild.

## Open Questions

Before I can proceed, I need two pieces of information to connect to your server:
1. **What is the IP address** of your Digital Ocean droplet? (Is it `143.198.207.144`?)
2. **What is the SSH username?** (e.g., `root`, `ubuntu`, or `gametech`)

*(Since you mentioned your SSH is set up on this laptop, I will be able to connect directly once you confirm the IP and user!)*

## Proposed Changes

---

### 1. Version Control
- We will stage all the deleted legacy files, the new `settings.py`, and the updated `docker` files.
- We will commit them with the message: `"Production cleanup: removing legacy files and optimizing Docker for Gunicorn/Whitenoise"`.
- We will push these changes to the `main` branch on GitHub.

### 2. Live Server Deployment
- I will use your laptop's SSH to connect to the Digital Ocean droplet.
- Navigate to the project directory on the server.
- Run `git pull origin main` to download the cleaned-up codebase.
- Run `docker-compose up -d --build` to safely rebuild the live containers with the new Gunicorn setup.

---

## Verification Plan

### Automated Tests
- I will check the Docker container logs on the server to ensure Gunicorn starts properly and there are no crash loops.

### Manual Verification
- We will visit the live website URL to confirm that it loads successfully, static files (CSS/JS) are rendering correctly, and the new Cignal Add-on feature we built earlier is live.
