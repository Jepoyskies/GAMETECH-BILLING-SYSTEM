# 🚀 GameTech Unli Fiber: System & Business Operations Summary

## 1. System Overview
The **GAMETECH Billing System** is a next-generation ISP billing and network management platform. It represents a massive leap forward from the previous legacy PHP architecture to a highly secure, scalable, and modern **Python/Django framework**. The system acts as the central brain for your business operations, tightly integrating billing, customer relationship management (CRM), and direct hardware control over MikroTik routers.

## 2. Core Modules & Functionality
The application is logically separated into three powerful modules:

### 💼 Billing & CRM (`billing` app)
- **Centralized Database**: A robust relational database schema handling Customers, Agents, Barangays, and Subscription Plans.
- **Role-Based Access Control (RBAC)**: Secure access levels for Admin, Technician, Agent, and CSR to ensure data privacy and operational security.
- **Payment Tracking & History**: Comprehensive tracking of payments, adjustments, and expiration dates.
- **Cignal Play Integration**: Bundles ISP services with digital TV, tracking Cignal Play account numbers and activation dates directly on the customer profile.
- **Geo-Mapping Ready**: Captures precise GPS coordinates (Latitude/Longitude) for every customer, allowing for visual geographical management and troubleshooting.

### 🌐 Network Manager (`network_manager` app)
- **Direct RouterOS Integration**: Uses a highly secure `RouterOS-api` wrapper to communicate with MikroTik core routers.
- **Real-time Diagnostics**: Fetches CPU/RAM usage, uptime, and crucial **optical SFP power readings** directly from the router to the dashboard.
- **Two-Way Synchronization**: Syncs PPPoE secrets and active sessions between the Django database and the physical router.
- **Uplink Monitoring**: Actively pings upstream (8.8.8.8) to determine uplink health, packet loss, and latency (ms), displaying it as Stable, Unstable, or Offline.

### 🧑‍💻 Customer Portal (`customer_portal` app)
- **Self-Service Dashboard**: Customers can log in using their PPPoE credentials to view their account status, current plan, and upcoming expiration dates.
- **Proactive Health Alerts**: If a Barangay, Sector (Router), or the specific customer is experiencing an outage or maintenance, the portal intelligently warns the user, reducing inbound CSR calls.
- **Statement of Account**: Customers can view and filter their payment history.
- **Mock Payments**: Foundation laid out for self-service payment gateway integrations.

---

## 3. Key Innovations & Business Operations Improvements

We didn't just build a billing system; we revolutionized how GameTech operates daily. Here are the biggest innovations:

> [!IMPORTANT]
> **Complete Modernization (The PHP to Django Migration)**
> We completely retired the fragile legacy PHP system (now safely tucked away in `_legacy_archive`). Moving to Django/Python provides enterprise-grade security, an Object-Relational Mapper (ORM) that prevents SQL injection, and a modular architecture that makes future updates infinitely easier.

> [!TIP]
> **Zero-Touch Automation: Auto-Suspension & Reactivation**
> Previously, suspending a user was manual and prone to errors. Now, when a customer's balance is overdue, the system **automatically injects L2 PADI drop rules** via `/interface bridge filter` on the MikroTik router and forcibly terminates their active session. Once they pay, the system instantly reactivates them. This enforces strict collections and boosts revenue collection without human intervention.

> [!NOTE]
> **Proactive Outage Management (Hierarchical Health Status)**
> Instead of customers calling blindly during an outage, we implemented a hierarchical health status. If a `Barangay` or `Router` is marked as "Outage" by a technician, all customers under that umbrella instantly see the outage notice on their portal. This drastically reduces support tickets and improves customer trust.

> [!TIP]
> **Remote Optical Diagnostics**
> Technicians no longer need to log into WinBox to check fiber health. The system pulls **SFP optical readings** and connection ping latency directly into the admin and customer portals. You can diagnose a bad fiber patch cord without leaving the CRM.

> [!IMPORTANT]
> **Idiot-Proof Deployment**
> We built `setup.bat` and `run.bat` scripts for Windows. New staff or admins can deploy the entire local server environment, install dependencies, configure the database, and run the system with a single double-click. No complex command-line knowledge required.

## 4. Summary of Impact
By tying the **Financial Data** directly to the **Hardware Access**, the GameTech Billing System eliminates revenue leakage, automates tedious manual router configurations, and provides a premium self-service experience to the end-users.
