import os

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"
SRC = os.path.join(ROOT, "billing", "templates", "billing", "live_monitoring.html")
DEST = os.path.join(ROOT, "billing", "templates", "billing", "live_monitoring")

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

print("Extracting live_monitoring partials...")

write_partial("_styles.html", 11, 393, "Styles")
write_partial("_hero.html", 397, 478, "Hero Section")
write_partial("_info_cards.html", 482, 595, "Info Cards")
write_partial("_live_traffic_card.html", 633, 661, "Live Traffic Card")
write_partial("_modal_apply_addon.html", 597, 631, "Apply Addon Modal")
write_partial("_modal_live_chart.html", 664, 683, "Live Chart Modal")
write_partial("_modal_view_all.html", 685, 696, "View All Modal")
write_partial("_modal_search_customer.html", 698, 736, "Search Customer Modal")
write_partial("_scripts.html", 740, len(lines), "Scripts")

orchestrator = r'''{% extends 'billing/base.html' %}
{% load static %}

{% block title %}Live Monitoring (NOC){% endblock %}

{% block extra_css %}
{% include "billing/live_monitoring/_styles.html" %}
{% endblock %}

{% block content %}
<div class="dashboard-container">
    {% include "billing/live_monitoring/_hero.html" %}

    <!-- Right Column Panels -->
    <div class="right-column">
        {% include "billing/live_monitoring/_info_cards.html" %}
        
        {% include "billing/live_monitoring/_live_traffic_card.html" %}
    </div>
</div>

{% include "billing/live_monitoring/_modal_apply_addon.html" %}
{% include "billing/live_monitoring/_modal_live_chart.html" %}
{% include "billing/live_monitoring/_modal_view_all.html" %}
{% include "billing/live_monitoring/_modal_search_customer.html" %}
{% include "billing/partials/update_health_modal.html" %}

{% endblock %}

{% block extra_js %}
{% include "billing/live_monitoring/_scripts.html" %}
{% endblock %}
'''

with open(SRC, "w", encoding="utf-8") as f:
    f.write(orchestrator)

print(f"Rewrote live_monitoring.html as orchestrator ({len(orchestrator.splitlines())} lines)")
