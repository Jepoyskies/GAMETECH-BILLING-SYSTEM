# Gametech Billing System - Development Update

### 1. Global UI/UX Modernization ("Gametech Premium" Standard)
- **Dark Mode Architecture:** Standardized all admin pages into a premium, responsive dark-mode aesthetic utilizing our custom `theme.css`. 
- **Card-Based Layouts:** Converted the legacy `service_plans.html` data table into a high-end, responsive **Pricing Card Grid** featuring dynamic upload/download indicators and floating action controls.
- **Modern Badges & UI Elements:** Upgraded all legacy status tags across `customer_list.html`, `live_monitoring.html`, and `add_on_payments.html` into Bootstrap 5 "subtle" badges (e.g., bright text on soft backgrounds) and glowing mesh gradients.
- **Navigation Control:** Injected a sleek, global **Back Button** directly into the `base.html` top navigation bar. This appears on every single page and tab to keep staff workflow tightly controlled within the application, preventing them from relying on unpredictable browser history controls.

### 2. Customer Portal Innovations (Revenue & Retention)
- **Proactive Alerts:** Engineered a dual-banner warning system on the `portal_dashboard.html` that automatically displays a Yellow banner for accounts expiring within 3 days, and a prominent Red banner for suspended accounts.
- **Passive Upselling:** Integrated "Cignal Play" and "Cignal Box" availability badges onto the dashboard with "+ Apply Now" prompts. This exposes all customers to these add-ons, driving passive revenue even if they haven't purchased them yet.
- **Business Rule Enforcement:** Enforced strict logic to allow automated online Plan Upgrades (triggering instant router reprovisioning upon payment), while completely hiding Plan Downgrades from the portal, forcing customers to contact Gametech support directly.

### 3. Backend Logic & Mikrotik Synchronization Fixes
- **Auto-Suspend Race Condition Resolved:** Discovered and patched a critical logical flaw in the midnight `auto_suspend.py` script. Previously, if the script dynamically learned a MAC address and called `.save()`, it inadvertently triggered the Mikrotik synchronization signal which instantly *re-enabled* the user. Implemented a direct `.update(mac_address=...)` bypass to guarantee 100% reliable suspensions.
- **Optimized Router API Calls:** Refactored `customer_portal/views.py` to remove duplicate/redundant Mikrotik API commands during the payment workflow. The system now strictly relies on the highly-efficient `post_save` background signal to upgrade profiles and kick sessions, significantly reducing router CPU load.
- **Complete Staff Accountability (Global Audit Tracker):** Addressed an issue where manual profile edits (e.g., changing a name or phone number) bypassed the logs. Engineered a robust `post_save` listener in `billing/signals.py` that intercepts *every* change to a customer profile. It automatically diffs the old and new states and generates a permanent `SystemLog` entry (e.g., `Phone: 09123 → 09999` or `Plan: 10Mbps → 50Mbps`), ensuring absolute transparency and accountability for all staff actions.
