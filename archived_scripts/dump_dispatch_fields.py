from dispatch.models import JobTicket, MonitoringRecord

for m in (JobTicket, MonitoringRecord):
    print("=" * 70)
    print(m.__name__)
    print("=" * 70)
    names = sorted({f.name for f in m._meta.get_fields() if hasattr(f, "name")})
    for i in range(0, len(names), 6):
        print("  " + "  ".join(f"{n:<22}" for n in names[i:i + 6]))
    print()
    # What the broken view asked for:
    for want in ("completed_at", "job_type", "concern", "source_tab",
                 "ticket_number", "created_at", "finished_at", "status",
                 "done_at", "time_accomplish", "team", "job_category"):
        print(f"   has {want:<16} : {hasattr(m, want)}")
    print()
