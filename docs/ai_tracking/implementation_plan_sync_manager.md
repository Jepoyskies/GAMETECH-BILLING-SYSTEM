# Sync Manager Redesign

This plan outlines the changes to completely redesign the Sync Manager UI and categorize users based on your requirements. The goal is to make the interface cleaner, more intuitive, and automatically flag suspicious activities (e.g., users added directly to Mikrotik by an insider without putting them in Django).

## Open Questions
1. **"Created today or created a long time ago but never did anything like payments"**: Since these suspicious users exist **only** in the Mikrotik router (not in the website/Django), we don't have access to their Django payment history. Is it acceptable if we flag them as suspicious based purely on their Mikrotik properties (e.g., weird username, missing full name/barangay in the comment, or using the 'default' profile)?
2. **Missing Users**: You didn't mention the current "Missing on Router" section (users that exist in Django but not in Mikrotik). I assume we should keep this section, just styled nicely, so you can still push missing users to the router. Is this correct?

## Proposed Changes

### 1. `network_manager/sync_services.py`
We will enhance the automatic detection of suspicious users. A Mikrotik-only user will be flagged as **Suspicious** if they meet ANY of the following criteria:
- **Weird Characters**: The username contains non-standard characters.
- **No Barangay/Full Name**: The comment field in Mikrotik is empty or doesn't follow the standard `Full Name | Barangay` format.
- **Default Profile**: They are assigned to the `default` profile instead of a proper paid plan profile.

#### [MODIFY] `sync_services.py`
- Update the `get_all_pppoe_users()` method to apply the new advanced suspicious detection logic mentioned above.

### 2. `network_manager/views.py`
We will update the backend logic that splits the users into categories before sending them to the UI.

#### [MODIFY] `views.py`
- Modify the `sync_manager` view to split the current `orphans` list into two distinct lists:
  - `mikrotik_only_clean`: Users in Mikrotik only, but they look like legitimate customers.
  - `mikrotik_only_suspicious`: Users in Mikrotik only, but they trigger the suspicious detection.

### 3. `network_manager/templates/network_manager/sync_manager.html`
We will completely overhaul the UI to make it look premium and easy to understand.

#### [MODIFY] `sync_manager.html`
- **Active Users**: Rename the "Synced Users" section to "Active Users".
- **Mikrotik Router Users**: A new section for clean Mikrotik-only users, with options to import them to Django.
- **Unknown/Suspicious Users**: A new highly visible red/warning section dedicated to suspicious Mikrotik-only users, making it easy to spot and delete them (or investigate insiders).
- **Missing Users**: Keep this section for users in Django but missing from Mikrotik, styled consistently with the rest.
- **UI Improvements**: Add premium styling, modern card designs, clear badges, and better table formatting matching the rest of the application's aesthetic.

## Verification Plan
1. **Automated Testing**: Ensure all lists render without 500 errors.
2. **Manual Verification**: 
   - Verify that users with weird names or missing comments are correctly routed to the **Unknown/Suspicious Users** tab.
   - Verify that legitimate orphans go to the **Mikrotik Router Users** tab.
   - Verify bulk import and delete actions still work flawlessly across the new sections.
