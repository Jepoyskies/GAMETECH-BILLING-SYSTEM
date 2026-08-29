# Fix Live Monitoring and Payment Add-on Bugs

## Overview
Based on your feedback, here are the proposed changes to fix the "Update Health" error, improve text readability in the live monitoring page, remove the scrollbars from the hardware telemetry section, and fix a bug in the payment add-on logs.

## Proposed Changes

### 1. Fix "Update Health" Action
**Issue:** Clicking the "Update Health" button currently does nothing (just reloads the page) because it's a simple link to a POST-only view.
**Fix:** 
- Convert the link into a button that opens a Bootstrap modal.
- Create an "Update Network Health" modal within `live_monitoring.html`.
- The modal will contain a form submitting to the `update_network_health` view, allowing you to select the scope (Router, Barangay, Customer), provide the health status, reason, and an option to send an SMS advisory.

### 2. Improve Text Readability
**Issue:** Some text elements in `live_monitoring.html` (like `.text-muted` on dark/blue backgrounds) lack contrast and are hard to read.
**Fix:** 
- Update the CSS to ensure `metric-label` and `metric-sub` have higher opacity (e.g. `rgba(255, 255, 255, 0.9)`).
- Replace overly dim text classes (`text-muted`) with clearer, higher-contrast alternatives in the Hardware Telemetry and Info Cell headers.

### 3. Remove "Scroll Scroll Thingy" in Hardware Telemetry
**Issue:** The hardware list container is constrained by a strict `max-height` causing ugly scrollbars to appear.
**Fix:** 
- Update `.info-cell` CSS so it is not strictly limited to `max-height: 280px`. We can remove this constraint or set `::-webkit-scrollbar` to `display: none` to hide the scrollbar track while maintaining clean layout.

### 4. Fix Expired Customers showing as Active (Bug)
**Issue:** In `payment_addon_logs.html`, expired customers are incorrectly badged as "Active". This happens because the `now` variable was not passed to the template from the view.
**Fix:**
- Update `payment_addon_logs_view` in `views.py` to include `'now': timezone.now()` in the template context.

## User Review Required
Please review the plan above. If you approve, I'll proceed with making the changes. Let me know if you want the hardware telemetry to not scroll at all (the box will grow taller to fit the content) or just to hide the ugly scrollbar!
