# System Enhancements & Fixes Implementation Plan

This plan addresses your 5 major requests: Winbox comment updates, exhaustive tracking, admin flexibility, payment reversion/transfer, and automated Cignal Box/Play application.

## Open Questions
- **Payment Reversion/Transfer:** When transferring a payment to the correct customer, should it completely subtract the extra days from the wrong customer, or do you also want to manually review their due date before saving? The system will attempt to automatically calculate the old due date based on the payment's `days_paid`, but for complex past payments, manual review might be safer.
- **Cignal Box UI:** I will add an "Approve & Apply" button directly on the "Add-on Requests" table and in the Notification dropdown. Is this the exact placement you had in mind?

## Proposed Changes

---

### 1. Winbox Comments Update

The logic for updating PPPoE comments on Mikrotik devices will be changed.

#### [MODIFY] `billing/views.py`
- Update `pay_customer_view` to change the `comment_text` format from `exp . new . plan...` to `paid (date) exp (date) . plan . method`.

#### [MODIFY] `customer_portal/views.py`
- Update `payment_callback` to use the same `paid (date) exp (date)` format for consistency when customers pay online.

---

### 2. Time & Date Tracking on All Logs & Notifications

We need to ensure every action has an exact timestamp visible to the Admin.

#### [MODIFY] `billing/templates/billing/logs.html`
- Update the table to format `changed_at` with time included (e.g., `Aug 28, 2026, 09:30 AM`).

#### [MODIFY] `billing/templates/billing/notifications.html`
- Update notification timestamps to show the exact time, not just the date or "time ago".

#### [MODIFY] `billing/templates/billing/view_customer.html`
- Ensure the Customer Audit Trail and Payment History tables display exact times for all records.

---

### 3. Admin Flexibility (Balance & Due Date)

The backend functions (`edit_customer_balance`, `edit_customer_expiration`) already exist, but we need to ensure the UI strictly allows the Admin (Sir Romnick) to modify these without restrictions.

#### [MODIFY] `billing/templates/billing/view_customer.html`
- Verify the "Edit Expiration" and "Edit Balance" modals are easily accessible to the Admin.
- Ensure the forms submit correctly and log the changes exhaustively in the `SystemLog`.

---

### 4. Revert / Transfer Payment (Wrong Reference Number)

This is a brand new feature to handle human error when staff apply payments to the wrong customer.

#### [NEW] `billing/views.py` (New Function: `revert_transfer_payment`)
- Create a new endpoint that takes a `payment_id` and a `new_customer_id`.
- **Logic:**
  - Locate the original (wrong) customer.
  - Subtract `days_paid` from their `expires_at`.
  - Add the `amount` back to their `outstanding_balance`.
  - Transfer the `Payment` record to the new (correct) customer.
  - Recalculate the new customer's `expires_at` and `outstanding_balance`.
  - Update Mikrotik for **both** customers (kick/suspend the wrong one if their new due date is past, and reactivate/comment the correct one).
  - Log everything in `SystemLog` and `AuditLog`.

#### [MODIFY] `billing/urls.py`
- Add route for `/payments/transfer/<int:payment_id>/`.

#### [MODIFY] `billing/templates/billing/payment_logs.html` (or view_customer)
- Add a "Transfer/Revert Payment" button next to recent payments (restricted to Admin).
- This opens a modal to select the correct customer and confirm the transfer.

---

### 5. Seamless Cignal Box & Play Application

Automating the approval process for Cignal requests so staff don't have to manually go to the "Edit Customer" page.

#### [MODIFY] `billing/views.py`
- Create an `approve_cignal_request` view. It will accept the `Cignal Play No.` and `Cignal Date`, update the `Customer` record automatically, and mark the `AddOnRequest` as Resolved.

#### [MODIFY] `billing/urls.py`
- Add route for `/cignal/approve/<int:request_id>/`.

#### [MODIFY] `billing/templates/billing/add_on_requests.html` (or notifications)
- Add an "Apply" button that triggers a modal.
- The modal will have inputs for "Cignal Play No." and "Cignal Date".
- Upon submission, it updates the customer automatically.

---

### 6. General System Audit & Error Fixes
- I will run automated checks (`python manage.py check`) and review the templates for any broken links, missing tags, or logical errors before and after execution to ensure a clean, amazing system.

## Verification Plan

### Manual Verification
1. Process a test payment and verify the Winbox comment format is `paid (date) exp (date)`.
2. View Logs and Notifications to confirm exact time and date are displayed.
3. As an Admin, modify a customer's balance and due date, ensuring it saves and logs.
4. Process a payment for Customer A, use the new "Transfer Payment" tool to move it to Customer B, and verify both customers' balances and due dates are correctly recalculated and Mikrotik is updated.
5. Create a Cignal Play request in the customer portal, and use the new "Apply" modal in the admin panel to automatically assign the Cignal Play Number.
