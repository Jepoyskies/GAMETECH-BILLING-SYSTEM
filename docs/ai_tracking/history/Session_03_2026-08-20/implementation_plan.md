# Advanced Billing Features & UX Upgrades

I have outlined a complete plan to implement all of your requests, giving you total control over the billing data and improving visibility for expiring accounts.

## 1. Upgraded Payment Logs UI
I will redesign the `payment_logs.html` page to be much more vibrant and easy to read.
- Introduce status badges for payment methods.
- Highlight the "Adjusted By" field so you clearly see what came from the "Customer Portal" vs "Admin".
- Improve the general table layout to match the modern aesthetic of the rest of the system.

## 2. Nearing Expiration Alerts & Filters
**For the Staff:**
- I will add quick-filter buttons (Tabs) to the top of the **Customers List**:
  - `All Customers`
  - `Nearing Expiration (<= 3 Days)`
  - `With Outstanding Balance`
  - `With Advance Payment`
- This will let you instantly see exactly who needs to be contacted.

**For the Customer:**
- If a customer is within 3 days of expiration, I will display a warning banner on their Customer Portal dashboard letting them know they need to renew soon to avoid disconnection.

## 3. Manual Overrides (Edit Expiration & Edit Balance)
I will add powerful override tools for the Staff on the `view_customer.html` page.
- **Edit Expiration Date:** A new button next to their expiration date that opens a modal to let you manually pick any date and time to override their expiration.
- **Edit/Reset Balance:** A new button next to their outstanding balance that lets you manually set it to `0` (reset), or input any specific outstanding/advance amount.
- **Audit Logging:** Both of these actions will be automatically logged to the `AuditLog` so you always know which staff member altered a customer's data and when.

Are you good with this plan to build out these features?
