import os

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"
SRC = os.path.join(ROOT, "billing", "templates", "billing", "view_customer.html")
DEST = os.path.join(ROOT, "billing", "templates", "billing", "view_customer")

os.makedirs(DEST, exist_ok=True)

with open(SRC, encoding="utf-8") as f:
    lines = f.readlines()

def write_partial(filename, line_start, line_end, header_comment=""):
    content = "".join(lines[line_start-1 : line_end])
    if header_comment:
        content = f"<!-- Base Partial: {header_comment} -->\n{content}"
    filepath = os.path.join(DEST, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created {filename} ({line_end - line_start + 1} lines)")

print("Extracting view_customer partials...")

write_partial("_styles.html", 8, 109, "Styles")
write_partial("_header_actions.html", 114, 236, "Header Actions & Alerts")
write_partial("_profile_header.html", 238, 253, "Profile Header")
write_partial("_info_cards.html", 255, 406, "Info Cards")
write_partial("_live_monitoring.html", 408, 445, "Live Monitoring & Map")
write_partial("_activity_logs.html", 447, 533, "Activity Logs")
write_partial("_modals.html", 535, 771, "Modals")
write_partial("_scripts.html", 776, len(lines)-1, "Scripts")

orchestrator = r'''{% extends "billing/base.html" %}
{% load static %}
{% load log_filters %}

{% block title %}View Customer: {{ customer.full_name }}{% endblock %}

{% block extra_css %}
{% include "billing/view_customer/_styles.html" %}
{% endblock %}

{% block content %}
<div class="container-fluid py-4 px-3 px-md-4">
    {% include "billing/view_customer/_header_actions.html" %}
    {% include "billing/view_customer/_profile_header.html" %}
    {% include "billing/view_customer/_info_cards.html" %}
    {% include "billing/view_customer/_live_monitoring.html" %}
    {% include "billing/view_customer/_activity_logs.html" %}
</div>

{% include "billing/view_customer/_modals.html" %}
{% endblock %}

{% block extra_js %}
{% include "billing/view_customer/_scripts.html" %}
{% endblock %}
'''

with open(SRC, "w", encoding="utf-8") as f:
    f.write(orchestrator)

print(f"Rewrote view_customer.html as orchestrator ({len(orchestrator.splitlines())} lines)")
