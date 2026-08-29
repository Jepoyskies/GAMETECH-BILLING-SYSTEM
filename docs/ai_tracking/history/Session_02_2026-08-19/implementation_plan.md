# Role-Based Access Control (RBAC) Implementation Plan

Based on my review of the codebase, the RBAC model (`SystemAdmin` with `role`) is partially set up, and some views like `edit_staff` are checking `user_role`, but it's not consistently enforced across the entire system.

This plan details how we will complete the RBAC implementation securely and systematically across all views and templates.

## Proposed Roles & Permissions
1.  **Admin (Superadmin)**: Full read/write/delete access across all modules, including Staff Management and System/Mikrotik Settings.
2.  **Editor**: Can manage day-to-day operations (Add/Edit/Delete Customers, Payments, Plans, Agents, NAP Boxes). **Cannot** manage Staff/Admins, and **cannot** manage Mikrotik router configurations.
3.  **Viewer**: Read-only access to view Customers, Payments, Dashboard, and Reports. **Cannot** add, edit, or delete any records.

## Open Questions
- Do you agree with the permissions mapped out above? If you need `Editor` to have access to the Network Manager/Router Settings, let me know.

## Proposed Changes

### `billing/decorators.py` (New File)
- **[NEW]** Create custom decorators to easily protect views throughout the application:
  - `@role_required(allowed_roles=['Admin', 'Editor'])`
  - This decorator will check `request.user.role`. If the user does not have the required role, it will show an error message and redirect them to the dashboard or previous page.

### `billing/views.py`
Apply the new decorators to enforce backend security.
- **Admin Only (`@role_required(['Admin'])`)**:
  - `add_staff`, `edit_staff`, `delete_staff`, `admin_panel_view`, `import_customers_csv`, `delete_all_payments_view`, `auto_suspend`, `backup_manager_view`, `mikrotik_view`.
- **Editor & Admin (`@role_required(['Admin', 'Editor'])`)**:
  - `add_customer`, `edit_customer`, `delete_customer`
  - `add_payment`, `edit_payment`, `delete_payment`
  - `add_plan`, `edit_plan`, `delete_plan`
  - `add_agent`, `edit_agent`, `delete_agent`
  - `add_account_type`, `edit_account_type`, `delete_account_type`
  - `send_semaphore_sms`
- **All Authenticated Staff (`@login_required` / No restrictions)**:
  - `dashboard_view`, `customers_view`, `view_customer`, `payments_view`, `plan_list`, `agent_list`, `report_view`.

### `network_manager/views.py`
Apply decorators to network management views.
- **Admin Only**:
  - `add_device`, `edit_device`, `delete_device`
- **Editor & Admin**:
  - `add_nap_view`, `edit_nap_view`, `delete_nap_view`, `sync_device_users`, `sync_manager`, `sync_push_user`, `sync_delete_user`
- **All Authenticated Staff**:
  - `device_list`, `nap_list_view`, `fbt_plc_calculator_view`, `test_device_connection`, `device_hardware_api`.

### UI/Template Updates (Front-end Security)
- **[MODIFY]** `base.html` (Sidebar): Hide "System Settings", "Staff / Admins", and "Network Manager" menu items from `Viewer` and `Editor` roles (as applicable).
- **[MODIFY]** `customers.html` / `view_customer.html`: Hide the "Add Customer", "Edit", and "Delete" buttons if the user is a `Viewer`.
- **[MODIFY]** `payments.html`: Hide "Add Payment", "Edit", and "Delete" buttons for `Viewers`.
- **[MODIFY]** `network_manager/device_list.html`: Hide "Add Device" and "Actions" dropdown from non-Admins.

## Verification Plan

### Manual Verification
1. Log in as a user with the **Viewer** role.
2. Verify that all "Add/Edit/Delete" buttons are hidden in the UI.
3. Attempt to manually access an restricted URL (e.g., `/add-customer/` or `/settings/admin-panel/`) to ensure the backend block correctly redirects with a permission error.
4. Repeat the process for the **Editor** role, ensuring they can edit customers but cannot access Admin settings.
5. Log in as an **Admin** to verify full access is retained.
