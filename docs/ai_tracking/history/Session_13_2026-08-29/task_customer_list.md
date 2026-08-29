# Customer List Enhancements

- `[x]` Update `billing/views.py` `customer_list` to add strict `Case/When` sorting based on status.
- `[x]` Update `billing/templates/billing/customer_list.html`:
  - `[x]` Rename filter button to "Expiring Soon (3 Days)".
  - `[x]` Update DataTables init to not override server-side ordering (`order: []`).
  - `[x]` Add row highlighting for expired/suspended customers.
  - `[x]` Improve badge and button styling.
- `[x]` Verify changes locally.
- `[ ]` Commit, push, and deploy to live server.
