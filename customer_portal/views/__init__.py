# customer_portal/views/__init__.py
# Re-exports all views so urls.py (from . import views) keeps working unchanged.
from .auth import portal_login, portal_logout, force_change_password
from .dashboard import portal_dashboard, portal_statement_view
from .payments import portal_process_mock_payment, portal_apply_addon, portal_cancel_addon
from .tickets import submit_ticket, portal_ticket_history
from .api import portal_router_uplink_api

__all__ = [
    "portal_login",
    "portal_logout",
    "force_change_password",
    "portal_dashboard",
    "portal_statement_view",
    "portal_process_mock_payment",
    "portal_apply_addon",
    "portal_cancel_addon",
    "submit_ticket",
    "portal_ticket_history",
    "portal_router_uplink_api",
]
