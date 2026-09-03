# Changelog

All notable changes to this project will be documented in this file.

## [2026-09-03]
### Added
- **Enhanced Expiration Tracking**: Added "Active", "Expiring", "Expired", and "Inactive" filter tabs to the Customer Portal (`customer_list.html`).
- **Dynamic Notification Templates**: Implemented an administrative UI (`message_templates.html`) for editing SMS and Email templates dynamically, utilizing `{customer_name}` and other placeholders.
- **Automated SLA Notifications**: Bound SLA auto-rebates in Celery tasks to trigger SMS and Email notifications to customers automatically upon application.
- **Service Monitoring (Downdetector)**: Developed a full NOC page (`downdetector.html`) displaying system uptime and latencies, alongside a real-time "System Health" widget inside the main dashboard.
- **Customer Live Traffic Graph**: Enhanced the individual Customer Profile view with a real-time animated Chart.js line graph to visualize live Rx/Tx Mbps.
- **Comprehensive Logging**: Consolidated System, Payment, Add-On, and Audit logs into a single view within the Customer Profile.
- **Payment Rollbacks**: Added administrative rollback features to safely revert payments and restore previous expiration dates.

### Fixed
- Fixed SMS notification bug in the Confirm Payment window where `customer.phone_number` was improperly referenced instead of `customer.phone`.

## [2026-09-01 & 2026-09-02]
### Added
- **Dispatch Monitoring System**: Initialized the Dispatch App (Phase 5) to manage repair workflows, job completions, and record tracking.
- **Verification Wizard**: Enhanced customer verification flows to standardize onboarding.
- **Premium Gametech Sync Manager**: Massive UI redesign with Auto-Fix Sync Button, reassurance prompts, and advanced conflict resolution.
- **Suspicious Account Tracking**: Added dynamic red badges, automated reasons, and a dedicated table for "Suspicious Accounts".
- **Security Check**: Added password protection modals to the Winbox Dashboard.

### Changed
- Refined UI tabs for customer service plans, including descriptions and visual organization.
- Replaced native browser alerts with custom Gametech interactive modals for a premium feel.
- Fixed DataTables warnings for empty tables.
- Updated login UI placeholders and removed dead forgot-password links.
- Corrected Mikrotik comment logic into signals to preserve PPPoE profile data accurately.

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
