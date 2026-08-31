# Changelog

All notable changes to this project will be documented in this file.

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
