# Advanced Billing & Data Override Walkthrough

I have successfully implemented all of the advanced billing features requested.

### 1. Payment Logs UI Upgrade
The Payment Logs page has been upgraded. The "Adjusted By" field now uses eye-catching badges:
- If a customer pays via the portal, it will display a **Green "Portal" Badge** with a globe icon.
- If an admin/staff processes the payment, it displays a **Blue Admin Badge** with a shield icon.
This allows you to scan the table and instantly see where payments are coming from.

### 2. Customers List Quick Filters
At the top of the **Customers List** page, you now have interactive, color-coded filter tabs:
- **All Customers** (Blue)
- **Nearing Expiration (<= 3 Days)** (Yellow)
- **With Outstanding Balance** (Red)
- **Paid in Advance** (Green)

Clicking these tabs instantly filters the table to show exactly the subset of customers you want to track or contact.

### 3. Customer Portal Expiration Warning
If a customer is logged into their portal and their account is set to expire within 3 days, a prominent red **"Expiring Soon!"** warning banner will automatically appear at the top of their screen, urging them to make a payment to avoid disconnection.

### 4. Admin Manual Overrides (Expiration & Balance)
When viewing a specific customer on the Admin side (`View Customer` page):
- You will see two new fields under **Basic Information**: `Expiration Date` and `Outstanding Balance` (which were previously hidden).
- Next to each, there is a small blue **Edit** icon (only visible to Admins and Editors).
- Clicking these icons opens a modal where you can force-edit the Expiration Date or manually reset/change the Outstanding Balance.
- **Audit Logging:** Any changes made via these manual overrides are securely logged to the system's Audit Logs so you can track who made the changes.
