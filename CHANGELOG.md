# Changelog

All notable changes to this project will be documented in this file.

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
