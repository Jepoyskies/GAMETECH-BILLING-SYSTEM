"""
Dispatch models package.

Split from a single 638-line models.py per AGENTS.md Rule 24 (400-line circuit
breaker). Re-exports every model so existing `from dispatch.models import X`
call sites keep working unchanged.

  core.py      Team, Technician, ConfigOption
  records.py   DispatchRecord, MonitoringRecord, JobDetail, AuditLog
  tickets.py   JobTicket, TicketTechnicianAssignment, JobTicketHistory,
               TicketBounceHistory, CallAttemptLog
"""
from .core import Team, Technician, ConfigOption
from .records import DispatchRecord, MonitoringRecord, JobDetail, AuditLog
from .tickets import (
    JobTicket,
    TicketTechnicianAssignment,
    JobTicketHistory,
    TicketBounceHistory,
    CallAttemptLog,
)

__all__ = [
    "Team", "Technician", "ConfigOption",
    "DispatchRecord", "MonitoringRecord", "JobDetail", "AuditLog",
    "JobTicket", "TicketTechnicianAssignment", "JobTicketHistory",
    "TicketBounceHistory", "CallAttemptLog",
]