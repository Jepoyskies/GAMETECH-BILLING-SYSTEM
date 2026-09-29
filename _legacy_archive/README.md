# Gametech Legacy PHP Billing System Archive

> **READ-ONLY HISTORICAL ARCHIVE**  
> This directory contains the original legacy PHP codebase of the Gametech Unli Fiber Billing & Management System, preserved for historical reference, logic comparison, and audit purposes.

---

## 📂 Contents Overview

### 1. Root Legacy Billing Scripts (`_legacy_archive/*.php`)
- `customers.php`: Legacy customer listing and management.
- `pay.php`, `pay_process.php`: Original payment processing and cash collection forms.
- `auto_suspend_pppoe_users.php`, `suspend_process.php`: Original automated suspension logic.
- `routeros_api.class.php`: PHP RouterOS API client for MikroTik communication.
- `mikrotik_devices.php`, `mikrotik_active_users.php`: Old router device management and PPPoE session monitor.
- `pppoe.php`, `pppoe_monitoring.php`: PPPoE secret management and telemetry.
- `subscription_plans.php`, `serviceplans.php`: Original plan configurations.
- `payment_logs.php`, `payment_addon_logs.php`, `payment_cignal_logs.php`: Old transaction log views.
- `geo_user_map.php`, `save_marker_positions.php`: Original subscriber map.

### 2. ISP & MikroTik Subsystem (`_legacy_archive/isp/`)
- `MikrotikManager/`: Router synchronization, geo mapping, and payment readjustment handlers.
- `cignal_play.php`, `cignalplay_form.php`: Legacy Cignal Play add-on modules.
- `add_on_payments.php`: Legacy add-on payments.
- `fbt_plc_calculator.php`: Fiber optical power / splitter budget calculator.
- `statement_of_account.php`: Legacy SOA generator.

---

## 🔒 Runtime Safety
- **Inert Status**: These files are completely excluded from the live Django execution stack, Gunicorn workers, and Celery beat runners.
- **Modern Replacement**: All business logic, billing computations, MikroTik API syncs, customer portals, and technician dispatch systems are actively managed by the modern Django 6.1 architecture (`billing/`, `network_manager/`, `customer_portal/`, `dispatch/`).
