# Winbox UI and Superuser Synchronization

This plan covers the implementation of a "Winbox UI" directly inside the Gametech Billing System, as well as fixing the superuser synchronization issue.

## 1. Superuser Synchronization

**Goal:** Ensure that whenever a superuser is created (e.g., via `python manage.py createsuperuser` or the Django admin), they automatically appear in the "Staff & Admins" list.

**Implementation Details:**
- Add a Django `post_save` signal for the `User` model in `billing/models.py`.
- Whenever a `User` is saved and `is_superuser` is `True`, the signal will automatically create or update the corresponding `SystemAdmin` record with the role `Admin`.

## 2. Winbox UI (Network Manager)

**Goal:** Provide an embedded Winbox-like dashboard for commonly used RouterOS features (PPPoE Secrets, Profiles, and Active Connections) so you don't have to switch to Winbox.

**Implementation Details:**

### A. Backend Services (`network_manager/services.py`)
Add robust methods to the `MikrotikAPI` class to handle RouterOS resources:
- `get_secrets()`, `add_secret()`, `update_secret()`, `delete_secret()`
- `get_profiles()`, `add_profile()`, `update_profile()`, `delete_profile()`
- `get_active_connections()`
- (We already have `kick_active_user()`, we will wire it up).

### B. New Views & Routing (`network_manager/urls.py` & `views.py`)
- `/network-manager/winbox/`: A landing page showing all active routers. Clicking a router takes you to its dashboard.
- `/network-manager/winbox/<int:device_id>/`: The main Winbox dashboard for a specific router. This page will have three main tabs (Secrets, Profiles, Active Connections).
- HTMX/AJAX endpoints for actions (e.g., Add Secret, Kick User, Delete Profile) so the UI feels snappy and responsive like a real desktop app.

### C. UI / Templates
- Add a new **"Winbox"** link under the **Network Ops** sidebar menu in `base.html`.
- Create `winbox_routers.html` (Router selection grid).
- Create `winbox_dashboard.html`. This will feature a sleek, dynamic UI with data tables and modals for adding/editing records.

## Open Questions
- Do you want the Winbox UI to have any specific permissions? (Currently planning to restrict it to `Admin` and `Technician` roles).
- For clearing all the data on the live server later, what exactly do you want cleared? Just Customers, Payments, and Logs, or do you also want to clear out Agents, Plans, and Network Devices? (We can run this script later, but I want to clarify in advance).
