# Customer List UI Enhancement & Ordering

This plan outlines the enhancements to completely revamp the Customer List page, making it visually amazing, strictly ordered, and highly intuitive for you and your staff.

## Proposed Changes

### 1. Smart Ordering System
We will update the backend to automatically sort all customers based on priority, rather than a random mix. The new priority order will be:
1. **Active (Paid)**: Customers currently connected and good standing.
2. **Pending**: New customers waiting for installation/activation.
3. **Suspended**: Customers who are temporarily disabled.
4. **Expired**: Customers whose plans have expired.
5. **Inactive / Pull Out**: Customers no longer with the service.

*Within each of these groups, they will be further sorted alphabetically by their First Name.*

#### [MODIFY] `billing/views.py`
- Add a Django `Case/When` annotation to the `customer_list` query to enforce this strict sorting order.

### 2. UI Refresh & "Nearing Expiration" Fix
We will redesign the customer list table and filters to look much cleaner and more premium.

#### [MODIFY] `billing/templates/billing/customer_list.html`
- **Fix the Filter Label**: Change `Nearing Expiration (<= 3 Days)` to a cleaner `Expiring Soon (3 Days)` or similar friendly text.
- **Enhanced Status Badges**: Redesign the status badges so they pop (e.g., bright solid green for Active, faded gray for Inactive, striking red for Expired).
- **Better Row Highlighting**: 
  - Expired and Suspended rows will have a subtle background tint (e.g., very light red or gray) so they immediately stand out from active customers without being overwhelming.
- **DataTables Initialization**: Update the JavaScript so that DataTables does **not** override our new custom backend ordering (by default DataTables sorts alphabetically, which ruins custom ordering).

## Verification Plan
1. **Automated Testing**: Load the customer list and verify the SQL query correctly orders the users.
2. **Manual Verification**: 
   - Visually confirm the button label is fixed.
   - Verify Active users appear at the top, followed by Pending, Suspended, Expired, and Inactive.
   - Check that the UI looks significantly more premium and readable.
