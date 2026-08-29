# Deployment Architecture & Hosting Strategy

Based on your business requirement—**"If the Mini PC is down, the system must still be up and customers can still pay"**—the Mini PC **cannot** be the main server. 

In the ISP business, your billing and payment portal is your cash register. If your cash register goes offline because someone tripped over a wire or there was a local power outage, you lose money and customer trust. 

Here is the breakdown of why a **Cloud-First** approach is the best method for your ISP, and how your Mini PC fits into the picture.

---

## ❌ Why the Mini PC Should NOT Be the Main Server

If you install the entire system (Database, Django Web App, Customer Portal) on the local Mini PC:
- **Single Point of Failure**: If power is lost, the internet connection drops, or someone unplugs the PC, the entire system goes dark. 
- **Customer Frustration**: Customers trying to pay their bills will see a "Website Cannot Be Reached" error. They won't be able to pay, and staff won't be able to log in to check records.
- **Security Risks**: To allow customers to access the Mini PC from the outside world, you have to open ports on your network (Port Forwarding/DDNS), making your local network vulnerable to hackers.

---

## ✅ The Recommended Method: Cloud-First Architecture

To achieve a professional, business-grade setup, **the Cloud must be your Main Server**.

### How it Works:
1. **The Cloud Server (Main)**: You host the Django billing system, PostgreSQL database, Redis, and Customer Portal on a reliable Cloud VPS (Virtual Private Server). 
2. **The Mini PC (The Bridge/Agent)**: The Mini PC sits in your office. It doesn't hold the database or the website. Instead, it acts as a secure "tunnel" (VPN) between the Cloud Server and your local MikroTik routers. 

### Why this is the best business decision:
- **100% Uptime for Payments**: Even if your entire office loses power and the Mini PC shuts off, the Customer Portal is safe in the cloud. Customers can still log in, view their invoices, and process payments.
- **Queued Operations**: If a customer pays while the Mini PC is off, the Cloud system records the payment. Once the Mini PC turns back on, the system will automatically communicate with the MikroTik routers to reconnect the customer's internet.
- **High Security**: The Cloud server is protected by professional data centers. Your local MikroTik routers don't need to be exposed to the public internet; they securely talk to the cloud via the Mini PC's VPN.

---

## 🛠️ Step-by-Step Implementation Plan

### 1. Choose a Cloud Hosting Provider (VPS)
Since you are using Docker, PostgreSQL, Redis, and Celery, you need a server with at least **2GB to 4GB of RAM**. 

**Recommended Providers:**
*   **DigitalOcean** (Basic Droplet - ~$12 to $24/month): Very easy to use, great for startups.
*   **Linode / Akamai** (~$12 to $24/month): Excellent performance and pricing.
*   **Hetzner Cloud** (~$5 to $10/month): The most cost-effective option with incredibly powerful servers, though their data centers are mostly in Europe/US (might add slight latency, but for a billing system, it's unnoticeable).
*   **AWS / Google Cloud**: Overkill and too expensive for this stage. Avoid them for now to keep costs low.

### 2. Set Up the Secure Connection (Tailscale)
How does the Cloud Server talk to the MikroTik routers if they aren't on the same network? **Tailscale**.

*   Install Tailscale on the Cloud VPS.
*   Install Tailscale on the Mini PC.
*   The Mini PC runs a "Subnet Router". This allows the Cloud Server to securely reach the local IP addresses of your MikroTik routers (e.g., `192.168.88.1`) as if they were sitting right next to each other.

### 3. What the Mini PC Actually Does Now
Your i3 1220p Mini PC is quite powerful. Since it won't be stressed running the main database, you can use it for:
*   **Network Monitoring**: Running tools like Zabbix or PRTG to monitor router health.
*   **Local Backups**: Periodically downloading database backups from the Cloud to have a physical copy on-site.
*   **The Secure Gateway**: Maintaining the 24/7 VPN tunnel (Tailscale/WireGuard) to the cloud.

---

## Summary of the "What Ifs"

> *"What will happen if someone unplugs the mini pc?"*
**Under the Cloud-First Model:** 
1. The billing website stays **ONLINE**.
2. Customers can still log in and pay.
3. Staff can still log in and view reports.
4. *The only thing that stops* is the system's ability to send immediate commands to the MikroTik router (like automatically reconnecting a user). Those commands will queue up in the cloud (via Celery) and execute the moment you plug the Mini PC back in.

## Next Steps
If you agree with this business approach, I recommend we:
1. Rent a small VPS (like DigitalOcean or Hetzner).
2. Deploy the current Dockerized system to that cloud server.
3. Install Tailscale on your local Mini PC to bridge the connection to your MikroTik routers.

Would you like to proceed with the Cloud-First approach? If so, which hosting provider would you like to explore?
