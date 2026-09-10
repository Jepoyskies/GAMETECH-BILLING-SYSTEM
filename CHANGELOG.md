# Changelog

All notable changes to this project will be documented in this file.

## [2026-09-10]
### Added
- **Shared Network Telemetry Engine (`NetworkMonitor`)**: Extracted unified network polling into `static/js/network_monitor.js` with exponential backoff and SweetAlert2 notifications.
- **Aider-Style Sniper System Guidelines**: Added `AGENTS.md` and `.agents/rules/sniper_aider_mode.md` to establish surgical token-conserving guidelines for all AI agents.
- **Lean Architecture Blueprint**: Created `make_architecture_dump.py` generating `gametech_architecture_map.txt` (~2,082 lines / ~8.5K tokens) replacing the 1M-token monolithic dump.

### Fixed
- **Live Monitoring & Router Uplink Freeze**: Added missing Select2 jQuery assets to `live_monitoring/_scripts.html` and updated regex in `billing/views/api/network.py` to parse floating-point RTTs.
- **Dashboard Caching 500 Error**: Fixed `UnboundLocalError` on `distinct_payers_this_month` and resolved timezone string parsing for cached metrics.
- **Repository Clutter Cleanup**: Archived 20+ ad-hoc diagnostic scripts into `archived_scripts/` and removed dead legacy Node/Express and Chart.js files.

## [2026-09-09]
### Added
- **Gametech Brand Identity & Light Mode**: Overhauled top navigation and sidebar to brand-aligned Light Mode with sleek bottom logout button and fixed active dropdown states.
- **Customer Portal Expiration Countdown**: Added animated color-coded countdown widget (green/yellow/red) for payment due dates.
- **Advance Payment Reset Security**: Added administrative password confirmation modal, red alert audit logging, and automated due date realignment.
- **Customizable Receipt SMS Templates**: Made receipt templates fully customizable via Settings with smart placeholders.
- **Live Monitoring Stability Heuristic**: Implemented connection stability scoring and status badges (Rock Solid, Stable, Flapping, Highly Unstable).
- **Modular Dashboard Architecture**: Decomposed `dashboard.html` into modular partials (`_stats.html`, `_charts.html`, `_modals.html`, `_scripts.html`) with Phase 2 Redis caching.

### Fixed
- **Payment Engine Stability**: Fixed `reverse` NameError in `pay_customer_view`, missing `calculate_new_expiration_date` import, and removed non-existent `customer` field from `SmsLog.objects.create()`.
- **Pre-Commit Suspension Evaluation**: Evaluated suspension status before saving payment to guarantee Mikrotik re-enable signals trigger immediately.
- **Portal Auth Redirection**: Fixed expired portal session redirect to point to `/portal/login/` instead of staff login.
- **Crash Recovery & Template Tag Fixes**: Fixed null byte file corruptions, injected missing `{% load static %}` across partials, and removed orphaned `{% endblock %}` tags.

## [2026-09-08]
### Added
- **Admin Control Center Overhaul**: Redesigned Admin Panel into a comprehensive 4-section Owner Control Center (Staff & Access, Billing Config, Network, System Tools).
- **Downdetector Full CRUD**: Dedicated Manage Downdetector Sites interface with inline Add, Edit, and Delete controls.
- **Mikrotik-Aware Rebates Engine**: Dynamic `expires_at` calculations and automated Mikrotik profile/status restoration upon SLA rebate credit.
- **Mikrotik-Aware Rollbacks & Transfers**: Reverting payments recalculates expiration dates and auto-suspends on the router if expired, wrapped in atomic database transactions.
- **Multi-Tier Live Monitoring**: Expanded monitoring to Overall, Per-Router (with bandwidth counters via `/interface/monitor-traffic`), and Per-Customer views.
- **Notification Toggles**: Added SMS and Email toggle switches to the payment confirmation modal.

## [2026-09-03]
### Added
- **Dynamic Live Monitoring Graph**: Integrated a beautifully animated `Chart.js` live traffic graph into the individual Customer Profile, visualizing real-time bandwidth usage (Rx/Tx Mbps).
- **Service Monitoring & Network Operations Center (NOC)**: Developed a full NOC dashboard page (`downdetector.html`) displaying global system uptime and latencies, alongside a real-time "System Health" widget natively inside the main admin dashboard.
- **Automated SLA Notifications**: Bound SLA auto-rebates in automated background tasks (Celery) to trigger localized SMS and Email notifications to customers automatically.
- **Dynamic Notification Templates**: Implemented an administrative UI (`message_templates.html`) for editing SMS and Email templates dynamically, utilizing `{customer_name}` and other smart placeholders.
- **Enhanced Expiration Tracking**: Added "Active", "Expiring", "Expired", and "Inactive" intelligent filter tabs to the Customer Portal (`customer_list.html`).
- **Comprehensive Logging & Auditing**: Consolidated System, Payment, Add-On, and Audit logs into a single centralized view within the Customer Profile to ensure absolute accountability.
- **Payment Rollbacks**: Added administrative rollback features to safely revert payments and dynamically restore previous account expiration dates in real-time.

### Fixed
- **System-Wide Server Errors**: Resolved a critical data-mapping bug (`changed_at` vs `created_at`) on the SystemLogs architecture that was previously causing widespread 500 Internal Server Errors across the application.
- **DigitalOcean CI/CD Pipeline Deployment**: Manually intervened to bypass faulty GitHub Actions workflows and forcefully restored parity on the DigitalOcean live server by rebuilding the Docker environment and `web` container, ensuring zero downtime and fully syncing the latest codebase.
- **SMS API Mapping**: Fixed an SMS notification bug in the Confirm Payment window where `customer.phone_number` was improperly referenced instead of the correct `customer.phone`.

## [2026-09-01 & 2026-09-02]
### Added
- **Dispatch Monitoring System (Phase 5)**: Initialized the full Dispatch application to seamlessly manage repair workflows, job completions, and technician record tracking.
- **Verification Wizard**: Enhanced customer verification flows to standardize onboarding and prevent bad data entry.
- **Premium Gametech Sync Manager**: Massive UI redesign with an Auto-Fix Sync Button, reassurance prompts, and advanced conflict resolution to seamlessly manage Mikrotik synchronization.
- **Suspicious Account Tracking**: Added dynamic red badges, automated reasons, and a dedicated table to isolate and track "Suspicious Accounts" autonomously.
- **Security Protocols**: Added strict password protection modals to the Winbox Dashboard to prevent unauthorized access.

### Changed
- **Modern Gametech Aesthetics**: Replaced all native browser alerts with custom Gametech interactive modals for a premium, sleek feel.
- **UI Architecture**: Refined UI tabs for customer service plans, including rich descriptions and visual organization.
- **Bug Fixes**: Fixed DataTables warnings for empty tables and updated login UI placeholders, removing dead forgot-password links.
- **Mikrotik Data Integrity**: Corrected Mikrotik comment logic into Django signals to preserve PPPoE profile data accurately without overriding user fields.

## [2026-08-31]
### Added
- Created a new sliding bottom-sheet UI for the mobile login page to eliminate scrolling.
- Added JavaScript `confirm()` alerts to all logout buttons (sidebar and profile dropdown) to prevent accidental logouts.
- Included the Gametech Unli Fiber copyright notice inside the login page.
- Added the happy GIMI mascot image (`gimi_happy.png`) to the login branding section.

### Changed
- **Major Refactor**: Split the monolithic `billing/views.py` into a structured module package (`billing/views/auth.py`, `customers.py`, etc.) for better maintainability.
- Updated the login page branding to use the official Gametech Unli Fiber logo (`logo_white.png`) instead of text.
- Overhauled mobile CSS scaling: Converted fixed pixel margins to viewport-relative (`vh`) units to prevent screen overflow and ensure the logo remains perfectly visible on small screens.
- Refined logo and text alignment: Applied `text-align-last: justify` to perfectly flush the tagline with the logo's width, and swapped the logo's box-shadow for a clean `drop-shadow` filter.
