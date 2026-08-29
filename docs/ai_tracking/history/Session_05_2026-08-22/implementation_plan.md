# Goal Description
The objective is to fix the missing "Paid but Offline" dashboard element and to improve the business workflow for handling Cignal Play / Add-on requests so that admins can actually apply the add-on to the customer profile rather than just clicking "Mark Resolved".

## Proposed Changes

### 1. Fix "Paid but Offline" Visibility
Currently, the "Paid but Offline" section completely disappears if there are no offline users. This makes the dashboard look broken or scattered.
- **Change:** I will update the javascript in `live_monitoring.html` to always display the "Paid but Offline" panel. If there are 0 users, it will display a clean success message (e.g., "All active users are online!"), ensuring the dashboard structure remains balanced and complete.

### 2. Improve Add-On Application Workflow
Currently, the Cignal Play add-on request just has a "Mark Resolved" button that dismisses the alert without letting the admin actually fulfill the request in the system.
- **Change:** I will change the button on the dashboard from "Mark Resolved" to "Process Application".
- **Change:** Instead of just dismissing the notification via AJAX, clicking "Process Application" will redirect the admin directly to the **Edit Customer** page for that specific user. From there, the admin can officially add the Cignal Play Account Number to their profile, adjust their billing plan, and manually manage the request just like a real-world business operation.

## Verification Plan
1. I will inspect `live_monitoring.html` to confirm the "Paid but Offline" panel stays visible with a 0 count.
2. I will confirm that clicking the Add-on request correctly redirects the user to the `edit_customer` view.
