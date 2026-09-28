# Gametech Billing System — Feature Inventory & Regression Audit

This document tracks every UI control, button, menu item, column, field, modal, export, bulk action, and JS behavior across the audited pages. In accordance with No-Regression Rules, every item must be PRESERVED on any modification.

---

## 1. Customers Directory (`/customers/`)
- **Orchestrator Template:** `billing/templates/billing/customer_list.html`
- **Partials:** `_hero.html`, `_filters.html`, `_table.html`, `_scripts.html`, `_styles.html`, `_modals.html`

### Inventory
| Category | Control / Feature | Current State | Notes |
|---|---|---|---|
| **Header / Hero** | Page Title & Subtitle | KEPT | "Customers Directory" |
| **Header / Filters** | Router Filter Dropdown (`#routerFilter`) | KEPT | Select device; updates table dynamically |
| **Header / Filters** | Barangay Filter Dropdown (`#barangayFilter`) | KEPT | Select barangay; updates table dynamically |
| **Header / CTA** | Add Customer Button (`add_customer`) | KEPT | Navigates to `/customers/add/` |
| **Header / Actions** | Quick Actions Dropdown | KEPT | Added in redesign |
| ↳ Quick Action | Export CSV (`export_customers_csv`) | KEPT | Downloads filtered CSV export |
| ↳ Quick Action | Bulk Edit Plan (`#bulkEditPlanModal`) | KEPT | Bulk reassigns selected customers |
| ↳ Quick Action | Transfer Router (`#bulkTransferModal`) | KEPT | Bulk migrates subscribers between Mikrotik devices |
| ↳ Quick Action | Activity Logs Offcanvas (`#customerLogsOffcanvas`) | KEPT | Slide-out panel for system logs |
| **KPI Stat Cards** | Total Subscribers Card (`?filter=all`) | KEPT | Filter link |
| **KPI Stat Cards** | Active Accounts Card (`?filter=active`) | KEPT | Filter link |
| **KPI Stat Cards** | Due Soon (<= 7D) Card (`?filter=expiring`) | KEPT | Filter link |
| **KPI Stat Cards** | Paid but Offline Card (`?filter=paid_offline`) | KEPT | Filter link |
| **KPI Stat Cards** | Expired (<= 7D) Card (`?filter=expired`) | KEPT | Filter link |
| **KPI Stat Cards** | Inactive (> 7D) Card (`?filter=inactive`) | KEPT | Filter link |
| **Table Filters** | Search Input (`#searchInput`) | KEPT | Text search with live DataTables debounce |
| **Table Filters** | Status Filter Dropdown (`#statusFilter`) | KEPT | All, Active, Expired, Suspended, Inactive, Pull Out |
| **Table Filters** | Connection Status Dropdown (`#connFilter`) | KEPT | All, Connected, Offline, Low, Poor, Unstable, Outage |
| **Table Filters** | Records Length Dropdown (`#lengthSelect`) | KEPT | 10, 25, 50, 100 per page |
| **Table Filters** | Reset Filters Button (`#resetFilters`) | KEPT | Clears all dropdowns and search inputs |
| **Table Columns** | 1. Checkbox Select All (`#selectAll`) | KEPT | Selects rows for bulk transfer/edit |
| **Table Columns** | 2. Full Name | KEPT | Displays name, PPPoE username, account type |
| **Table Columns** | 3. Email | KEPT | Displays email |
| **Table Columns** | 4. Phone | KEPT | Monospace formatted contact number |
| **Table Columns** | 5. Plan | KEPT | Subscription plan name and monthly price |
| **Table Columns** | 6. Agent | KEPT | Linked sales agent name |
| **Table Columns** | 7. Barangay | KEPT | Assigned barangay |
| **Table Columns** | 8. Router | KEPT | Assigned Mikrotik device |
| **Table Columns** | 9. Status | KEPT | Dual badge: Lifecycle status + Live MT status dot |
| **Table Columns** | 10. Actions | KEPT | Row action buttons |
| **Row Actions** | View Profile (`view_customer`) | RESTORED / KEPT | Eye icon button (`gt-icon-btn`) |
| **Row Actions** | File Repair Ticket (`#modal-customer-repair`) | RESTORED | Direct visible button (`gt-icon-btn`), restored from dropdown |
| **Row Actions** | Edit Details (`edit_customer`) | RESTORED / KEPT | Pencil icon button (`gt-icon-btn`, Admin/Editor) |
| **Row Actions** | Delete Customer (`delete_customer`) | RESTORED | Direct visible button with confirmation (`gt-icon-btn--danger`, Admin/Editor), restored from dropdown |

---

## 2. Customer Subscriptions (`/subscriptions/`)
- **Orchestrator Template:** `billing/templates/billing/subscription_plans.html`
- **Partials:** `billing/templates/billing/partials/subscription_plans_table.html`

### Inventory
| Category | Control / Feature | Current State | Notes |
|---|---|---|---|
| **KPI Cards** | Active Subscribers Filter Card | KEPT | `subsSetFilter('status', 'active')` |
| **KPI Cards** | Expiring Soon Filter Card | KEPT | `subsSetFilter('status', 'expiring')` |
| **KPI Cards** | Paid but Offline Filter Card | KEPT | `subsSetFilter('status', 'paid_offline')` |
| **KPI Cards** | Connected to Router Filter Card | KEPT | `subsSetFilter('connection', 'Connected')` |
| **KPI Cards** | Disconnected / Offline Filter Card | KEPT | `subsSetFilter('connection', 'Not Connected')` |
| **KPI Cards** | Expired Filter Card | KEPT | `subsSetFilter('status', 'expired')` |
| **KPI Cards** | Inactive Filter Card | KEPT | `subsSetFilter('status', 'inactive')` |
| **Toolbar** | Search Input (`#subs-search`) | KEPT | Full-text search |
| **Toolbar** | Status Filter Dropdown (`#subs-status`) | KEPT | Status filter |
| **Toolbar** | Connection Dropdown (`#subs-connection`) | KEPT | Live connection state |
| **Toolbar** | Reset Filter Button (`#btn-subs-reset`) | KEPT | Restores default view |
| **Bulk Actions** | Send Bulk SMS Button & Modal (`#bulkSmsModal`) | KEPT | SMS bulk delivery modal |
| **Bulk Actions** | Send Bulk Email Button & Modal (`#bulkEmailModal`) | KEPT | Email bulk delivery modal |
| **Table Columns** | 1. Checkbox Select All (`#selectAll`) | KEPT | Multi-row selector |
| **Table Columns** | 2. Subscriber Details | KEPT | Name, PPPoE username, address, phone |
| **Table Columns** | 3. Billing & Plan | KEPT | Plan name, price, expiry date, status badge |
| **Table Columns** | 4. Network Status | KEPT | Live MikroTik IP, MAC, signal status |
| **Table Columns** | 5. Actions | KEPT | Primary button + dropdown menu |
| **Row Actions** | Pay Button (`pay_customer`) | KEPT | Direct shortcut to payment screen |
| **Row Actions** | More Actions Dropdown (`.subs-more-btn`) | KEPT | Dropdown menu toggle |
| ↳ More Action | View Profile (`view_customer`) | KEPT | Opens customer profile |
| ↳ More Action | Rebate (`customer_rebate`) | KEPT | Opens rebate application |
| ↳ More Action | Rollback (`customer_rollback`) | KEPT | Opens transaction rollback form |
| ↳ More Action | Statement of Account (`statement_of_account`) | KEPT | Opens SOA in new tab |
| ↳ More Action | System Logs (`system_logs`) | KEPT | Filtered audit log query |
| ↳ More Action | Rebate Logs (`rebates_logs`) | KEPT | Filtered rebate log query |

---

## 3. Cignal Play Dashboard & Subscriptions Table (`/cignal-play/`)
- **Orchestrator Template:** `billing/templates/billing/cignal_dashboard.html`
- **Partials:** `_active_subscriptions.html`, `_pending_applications.html`, `_recent_logs.html`, `_styles.html`, `_scripts.html`

### Inventory
| Category | Control / Feature | Current State | Notes |
|---|---|---|---|
| **KPI Hero Cards** | Total Active Subscriptions | KEPT | Hero metric |
| **KPI Hero Cards** | Expiring Soon (< 7 Days) | KEPT | Amber status metric |
| **KPI Hero Cards** | Overdue Accounts | KEPT | Red status metric |
| **KPI Hero Cards** | Monthly Recurring Revenue (MRR) | KEPT | Currency metric |
| **Tabs** | Active Subscriptions Tab | KEPT | Renders active accounts table |
| **Tabs** | Overdue Accounts Tab | KEPT | Renders overdue accounts table |
| **Tabs** | All Subscriptions Tab | KEPT | Complete subscriber directory |
| **Tabs** | Pending Applications Tab | KEPT | Waiting staff approval |
| **Tabs** | Recent Activity Logs Tab | KEPT | Audit events |
| **Active Table Columns** | Customer, Subscription, Status, Actions | KEPT | Consolidated responsive columns |
| **Overdue Table Columns** | Customer, Subscription, Status, Actions | KEPT | Consolidated responsive columns |
| **All / Subscriptions Table Columns** | Customer, Subscription, Status, Date Applied, Adjusted By, Actions | RESTORED | Restored standalone "Adjusted By" column (`<th>Adjusted By</th>`) |
| **Row Actions** | Edit Details (`openCignalEditModal`) | KEPT | Icon button |
| **Row Actions** | Record Payment / Reload (`openCignalPaymentModal`) | KEPT | Icon button |
| **Row Actions** | Mark Pulled-Out / Remove (`cancel_cignal_subscription`) | RESTORED | Restored to direct visible button (`gt-icon-btn--danger`) with confirmation; dropdown kept only for View Customer Profile |

---

## 4. Dispatch Dashboard and Subpages
- **Templates:**
  - `dispatch/templates/dispatch/dashboard.html`
  - `dispatch/templates/dispatch/dispatch_monitoring.html` (Master Log)
  - `dispatch/templates/dispatch/internet_install.html` (Internet Install)
  - `dispatch/templates/dispatch/client_concerns.html` (Client Concerns)
  - `dispatch/templates/dispatch/management.html` (Management)
  - `dispatch/templates/dispatch/audit_log.html` (Audit Log)

### Inventory
| Page | Control / Feature | Current State | Notes |
|---|---|---|---|
| **Dashboard** | KPI Hero Cards (Pending, Ongoing, Done, Targets) | KEPT | Real-time metric cards |
| **Dashboard** | Operational Overview (Charts & Graphs) | KEPT | Daily performance visualization |
| **Dashboard** | Shared Nav Tabs (Master Log, Install, Concerns, Mgmt, Audit) | KEPT | Standard navigation across dispatch |
| **Dashboard** | Pipeline Stage 1/2/3 Buttons | REMOVED / REPLACED | Replaced by unified Dispatch Queue (`dispatch_queue`) in Phase 4A |
| **Master Log** | 17-Column Dispatch Monitoring Table | EXPANDED | Expanded from 7 legacy columns to 17 standard ISP columns |
| **Master Log** | Filter Bar (Search, CSR, Source, Status, Reset) | KEPT | Comprehensive filtering |
| **Master Log** | Export / Print Options | KEPT | Export functionality |
| **Internet Install** | 2-Tab Split (Pending vs Ongoing) | EXPANDED | Upgraded from 1 flat table to 2 operational subtabs |
| **Internet Install** | Quick Dispatch Modal Button | KEPT | Opens assignment modal |
| **Client Concerns** | 2-Tab Split (Pending vs Ongoing) | EXPANDED | Upgraded from 1 flat table to 2 operational subtabs |
| **Client Concerns** | New Concern Button & Modal (`#modal-add-concern`) | KEPT | Customer concern intake |
| **Management** | Tab 1: Staff & Accounts (`_management_accounts.html`) | MOVED | Refactored into partial; all forms/lists kept |
| **Management** | Tab 2: Teams & Technicians (`_management_teams_techs.html`) | MOVED | Refactored into partial; team creation kept |
| **Management** | Tab 3: Monthly Targets (`_management_targets.html`) | MOVED | Refactored into partial; quota editing kept |
| **Management** | Tab 4: Dropdowns / Options (`_management_dropdowns.html`) | MOVED | Refactored into partial; add/edit/delete option modals kept |
| **Audit Log** | Metric Cards (Total, Creates, Updates, Deletes) | KEPT | Audit summary metrics |
| **Audit Log** | Action Filters (ALL, CREATE, UPDATE, DELETE) | KEPT | Filter buttons |
| **Audit Log** | Entity Filter Dropdown (`select[name=entity]`) | KEPT | Dropdown filter |
| **Audit Log** | Search Input (`input[name=q]`) | KEPT | Audit log search |
| **Audit Log** | Expandable Diff Row Details | KEPT | State transition inspection |

---

## 5. Add Customer (`/customers/add/`)
- **Template:** `billing/templates/billing/add_customer.html`

### Inventory
| Category | Control / Feature | Current State | Notes |
|---|---|---|---|
| **Form Inputs** | Full Name (`input[name=full_name]`) | KEPT | Required text input |
| **Form Inputs** | Email Address (`input[name=email]`) | BEHAVIOR CHANGED | Changed from required to optional (rural subscribers) |
| **Form Inputs** | Phone Number (`input[name=phone]`) | KEPT | Required contact number |
| **Form Inputs** | Address (`input[name=address]`) | KEPT | Street address |
| **Form Inputs** | Barangay Dropdown (`select[name=barangay_id]`) | KEPT | Required selection |
| **Form Inputs** | Sales Agent Dropdown (`select[name=agent_id]`) | KEPT | Optional sales representative attribution |
| **Actions** | Cancel Link (`btn-cancel`) | KEPT | Returns to customer list or `next` URL |
| **Actions** | Submit Button (`button[type=submit]`) | KEPT | Form submission button |
| **Onboarding** | Onboarding Verification Checklist & Decline Modal | KEPT | Added in Phase 3/4 pipeline |

---

## 6. Renew / Pay Bill (`/customer/<username>/pay/`)
- **Template:** `billing/templates/billing/pay_customer.html`

### Inventory
| Category | Control / Feature | Current State | Notes |
|---|---|---|---|
| **All Controls** | Plan Selector, Upgrade Fee, Wallet Deduction, Submit Payment | KEPT | 100% identical to baseline (0 diff) |

---

## 7. Message Templates (`/settings/templates/`)
- **Template:** `billing/templates/billing/message_templates.html`

### Inventory
| Category | Control / Feature | Current State | Notes |
|---|---|---|---|
| **All Controls** | Template List, Smart Tags Picker, Live Preview, Edit Modals | KEPT | 100% identical to baseline (0 diff) |

---

## 8. Agent Pages (`/agents/`, `/agents/view/<id>/`, `/agent-dashboard/`)
- **Templates:** `billing/templates/billing/agents.html`, `billing/templates/billing/view_agent.html`, `billing/templates/billing/agent_portal/`

### Inventory
| Category | Control / Feature | Current State | Notes |
|---|---|---|---|
| **Agents List** | Search Input (`#agentSearchInput`) | KEPT | Search bar in table toolbar |
| **Agents List** | Add Agent Modal (`#modal-add-agent`) | KEPT | Modal form for creating agents |
| **Agents List** | Dashboard Back Link (`dispatch_dashboard`) | RESTORED | Restored secondary header button (`gt-btn-secondary`) |
| **Agents List** | Stats Bar (4 KPI Hero Cards) | RESTORED | Restored 4 executive metric cards (`gt-kpi-card`: Total, Active, Referrals, Commission) |
| **Agents List Table** | Columns: Name, Contact, Customers, Payout, Commission, Actions | KEPT | Responsive table layout |
| **Contact Column** | One-Click Copy Actions (`copyText`) | RESTORED | Restored one-click clipboard copy buttons for email and phone |
| **Row Actions** | View Agent Profile (`view_agent`) | KEPT | Eye icon button |
| **Row Actions** | Edit Agent (`edit_agent`) | KEPT | Pencil icon button |
| **Row Actions** | Delete Agent (`delete_agent`) | KEPT | Direct icon button with confirmation dialog |
| **Row Actions** | Mobile Separate Cards Layout | REMOVED | Consolidated into responsive DataTables view (purely visual) |
| **Agent View** | Profile details, referred customers table, commission log | KEPT | All features preserved |
| **Agent Portal** | Prospect submission, commission cashout request | KEPT | All portal features preserved |

---

## 9. Customer View (`/customers/view/<id>/`)
- **Templates:** `billing/templates/billing/view_customer.html` and partials

### Inventory & Audit Findings
| Control | Pre-Redesign State | Current State | Status |
|---|---|---|---|
| Statement of Account | Link in More Actions | Link in More Actions | KEPT |
| Update Health | Button in More Actions | Button in More Actions | KEPT |
| Send SMS | Button in More Actions | Button in More Actions | KEPT |
| Send Email | Button in More Actions | Button in More Actions | KEPT |
| Rebate | Link in More Actions | Link in More Actions | KEPT |
| Rollback | Link `<a href="{% url 'customer_rollback' %}">` | Direct link `<a href="{% url 'customer_rollback' %}">` without redundant SweetAlert popup | KEPT / FIXED (Preserves original route & form confirmation) |
| Kick Session | Form in More Actions | Form in More Actions | KEPT / FIXED (Unclipped via CSS scroll/z-index; annotated with Read-Only Mode badge when ROUTER_MODE=read_only) |
| Force Suspend | Form in More Actions | Form in More Actions | KEPT / FIXED (Unclipped via CSS scroll/z-index; annotated with Read-Only Mode badge when ROUTER_MODE=read_only) |
| Force Reactivate | Button in More Actions | Button in More Actions | KEPT / FIXED (Unclipped via CSS scroll/z-index; annotated with Read-Only Mode badge when ROUTER_MODE=read_only) |
| Delete Customer | Form in More Actions (Admin role) | Form in More Actions (`perms.billing.delete_customer or is_superuser`) | KEPT / FIXED (Unclipped via CSS scroll/z-index; permission-based check allows anyone permitted to delete) |

---

## 10. Agent Incentive Engine & Payouts (`/agents/payouts/`, `/agent-dashboard/`)
- **Templates:** `billing/templates/billing/payouts/index.html`, `billing/templates/billing/agent_portal/dashboard.html`
- **Views:** `billing/views/payouts.py`, `billing/views/agents.py`
- **Services:** `billing/services/incentives.py`

### Inventory & Capabilities
| Feature / Control | Capability | Status |
|---|---|---|
| **2nd Month Qualification** | Automatically detects when 2nd month is paid (renewal, 2+ month upfront advance, or cumulative partials $\ge$ 2x plan price). Excludes one-time fees (₱500 GIMI upgrade fee). | ADDED / VERIFIED |
| **Exclusions & Cancellations** | Legacy, router-sync, and non-agent customers excluded. Cancelled before qualifying never counts; already-qualified preserved. | ADDED / VERIFIED |
| **Revocation on Rollback** | Revokes qualification event if payment rollback brings net paid below 2x plan price prior to payout. Re-qualifies upon subsequent payment. | ADDED / VERIFIED |
| **Idempotency** | Re-saving payments or re-evaluating customers never creates duplicate events. | ADDED / VERIFIED |
| **Admin Payout Screen** | `/agents/payouts/` lists agents with $\ge$ 5 qualified customers; shows pending approval batches and permanent ledger. | ADDED / VERIFIED |
| **Batch Creation** | Multiples of 5 (FIFO oldest qualified first); links to `AgentPayoutBatch` and `AgentQualificationEvent.payout_batch`; extras cleanly carry over. | ADDED / VERIFIED |
| **Mark Paid** | Records `paid_by`, `paid_at`, and `reference_no`; transitions batch to `paid` and events to `paid_out`. Permanent record preserved. | ADDED / VERIFIED |
| **Agent Portal Wallet & Progress** | Progress toward next 5 (`progress / 5`), progress bar, and claimable balance in Agent Portal. | ADDED / VERIFIED |
| **Referrals Payment Progress** | Shows progress for qualifying month (e.g. `PHP 100 paid, PHP 900 remaining`), unlock date, and due date while preserving privacy. | ADDED / VERIFIED |
| **Permanent Payout Ledger** | Agent portal reads completed batches directly from permanent ledger. | ADDED / VERIFIED |

