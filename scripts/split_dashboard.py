"""Split dashboard.html into partial templates using Django {% include %} pattern."""
import os

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"
SRC = os.path.join(ROOT, "billing", "templates", "billing", "dashboard.html")
DEST = os.path.join(ROOT, "billing", "templates", "billing", "dashboard")

os.makedirs(DEST, exist_ok=True)

with open(SRC, encoding="utf-8") as f:
    lines = f.readlines()

# Line ranges are 1-indexed in the mapping, convert to 0-indexed for slicing
# After reading the full file, here's the section map:
# Lines 1-5:   Header (extends, load, title)
# Lines 6-879: {% block extra_css %} ... {% endblock %} (all CSS)
# Lines 880:   (blank)
# Lines 881-882: {% block content %} + wrapper div open
# Lines 883-903: Hero banner
# Lines 904-968: KPI cards (Revenue, Customers, Collection)
# Lines 969-1050: Secondary KPI totals (Today, Yesterday, Week, Month, Year)
# Lines 1051-1069: Sales overview chart
# Lines 1070-1071: Git merge conflict marker (<<<<<<< HEAD) - needs cleanup
# Lines 1072-1163: Old KPI rows + old sales chart (between conflict markers)
# Lines 1164-1241: Charts + Admin Logins row (weekly, pie, admin logins, uptime)
# Lines 1242-1258: Downdetector system health widget
# Lines 1259-1307: Expiring soon alert
# Lines 1308-1485: Bottom widgets (recent logins, top clients, popular plans, expiring soon)
# Lines 1486-1533: Top Clients Modal
# Lines 1534-1593: Recent Logins Modal
# Lines 1594-1651: Popular Plans Modal
# Lines 1652-1713: Expiring Soon Modal
# Lines 1714-1746: Revenue Growth Modal
# Lines 1747-1787: New Customers Modal
# Lines 1788-1836: Collection Rate Modal
# Lines 1837-1933: Revenue Breakdown Modals (looped)
# Lines 1934-1935: Close wrapper divs
# Lines 1936-2241: Legacy hidden dashboard (display: none) - CAN BE DELETED
# Lines 2242: {% endblock %}
# Lines 2243-2774: {% block extra_js %} ... scripts ... {% endblock %}

def write_partial(filename, line_start, line_end, header_comment=""):
    """Write lines[line_start-1 : line_end] to a partial file."""
    content = "".join(lines[line_start-1 : line_end])
    if header_comment:
        content = f"<!-- Dashboard Partial: {header_comment} -->\n{content}"
    filepath = os.path.join(DEST, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    line_count = line_end - line_start + 1
    print(f"  Created {filename} ({line_count} lines)")

print("Extracting dashboard partials...")

# 1. Styles (all CSS inside extra_css block)
write_partial("_styles.html", 7, 878, "All Dashboard CSS")

# 2. Hero Banner
write_partial("_hero_banner.html", 885, 903, "Hero Banner")

# 3. KPI Cards (Revenue, Customers, Collection)
write_partial("_kpi_cards.html", 904, 968, "Primary KPI Cards")

# 4. KPI Totals (Today/Yesterday/Week/Month/Year)
write_partial("_kpi_totals.html", 970, 1050, "Secondary KPI Totals")

# 5. Sales Overview Chart
write_partial("_chart_sales.html", 1052, 1069, "Sales Overview Chart")

# 6. Charts + Admin Logins Row (weekly, pie, admin logins + uptime)
write_partial("_charts_and_logins.html", 1165, 1241, "Charts and Admin Logins Row")

# 7. System Health Widget
write_partial("_system_health.html", 1243, 1258, "Downdetector System Health")

# 8. Expiring Soon Alert
write_partial("_expiring_soon_alert.html", 1261, 1307, "Expiring Soon Alert")

# 9. Bottom Row Widgets (recent logins, top clients, popular plans, expiring)
write_partial("_bottom_widgets.html", 1309, 1485, "Bottom Row Widgets")

# 10. Modal - Top Clients
write_partial("_modal_top_clients.html", 1486, 1533, "Top Clients Modal")

# 11. Modal - Recent Logins
write_partial("_modal_recent_logins.html", 1535, 1593, "Recent Logins Modal")

# 12. Modal - Popular Plans
write_partial("_modal_popular_plans.html", 1595, 1651, "Popular Plans Modal")

# 13. Modal - Expiring Soon
write_partial("_modal_expiring_soon.html", 1653, 1713, "Expiring Soon Modal")

# 14. Modal - Revenue Growth
write_partial("_modal_revenue.html", 1715, 1746, "Revenue Growth Modal")

# 15. Modal - New Customers
write_partial("_modal_customers.html", 1748, 1787, "New Customers Modal")

# 16. Modal - Collection Rate
write_partial("_modal_collection.html", 1789, 1836, "Collection Rate Modal")

# 17. Modal - Revenue Breakdowns (looped)
write_partial("_modal_breakdowns.html", 1838, 1933, "Revenue Breakdown Modals")

# 18. Scripts (all JS)
write_partial("_scripts.html", 2244, 2774, "All Dashboard JavaScript")

# Now write the new orchestrator dashboard.html
orchestrator = r'''{% extends 'billing/base.html' %}
{% load static %}

{% block title %}Dashboard | Gametech Unli Fiber{% endblock %}

{% block extra_css %}
<style>
{% include "billing/dashboard/_styles.html" %}
</style>
{% endblock %}

{% block content %}
<!-- New UI Build Area -->
<div class="container-fluid py-4 px-3 px-md-4 dashboard-wrapper" id="new-dashboard-ui">

  {% include "billing/dashboard/_hero_banner.html" %}

  {% include "billing/dashboard/_kpi_cards.html" %}

  {% include "billing/dashboard/_kpi_totals.html" %}

  {% include "billing/dashboard/_chart_sales.html" %}

  {% include "billing/dashboard/_charts_and_logins.html" %}

  {% include "billing/dashboard/_system_health.html" %}

  {% include "billing/dashboard/_expiring_soon_alert.html" %}

  {% include "billing/dashboard/_bottom_widgets.html" %}

  {% include "billing/dashboard/_modal_top_clients.html" %}

  {% include "billing/dashboard/_modal_recent_logins.html" %}

  {% include "billing/dashboard/_modal_popular_plans.html" %}

  {% include "billing/dashboard/_modal_expiring_soon.html" %}

  {% include "billing/dashboard/_modal_revenue.html" %}

  {% include "billing/dashboard/_modal_customers.html" %}

  {% include "billing/dashboard/_modal_collection.html" %}

  {% include "billing/dashboard/_modal_breakdowns.html" %}

</div>
{% endblock %}

{% block extra_js %}
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2"></script>
{% include "billing/dashboard/_scripts.html" %}
{% endblock %}
'''

# Write the new orchestrator
with open(SRC, "w", encoding="utf-8") as f:
    f.write(orchestrator)

orchestrator_lines = len(orchestrator.strip().split("\n"))
print(f"\n  Rewrote dashboard.html as orchestrator ({orchestrator_lines} lines)")
print(f"  Created {len(os.listdir(DEST))} partial files in dashboard/")
print("\nDone! Run 'python manage.py check' to verify.")
