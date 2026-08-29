# Live Monitoring Overhaul Tasks

- `[x]` **1. Fix "Paid but Offline" Widget**
  - `[x]` Modify `renderOfflineCustomers()` in `live_monitoring.html`.
  - `[x]` If array is empty, force `display: flex` instead of `none`.
  - `[x]` Inject a UI state indicating all users are online instead of an empty list.

- `[x]` **2. Improve Cignal Play Workflow**
  - `[x]` Modify `loadAddonRequests()` in `live_monitoring.html`.
  - `[x]` Change the `Mark Resolved` button to `Process Application`.
  - `[x]` Wrap it in an `<a href="/billing/customers/${req.customer_id}/edit/">` link.
  - `[x]` Add a `?resolve_addon=${req.id}` query parameter.

- `[x]` **3. Auto-Resolve on Edit**
  - `[x]` In `edit_customer.html`, add JS to detect `?resolve_addon`.
  - `[x]` Trigger an AJAX call to automatically mark the addon request as resolved while the admin fills out the form.
