import os

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"
SRC = os.path.join(ROOT, "customer_portal", "templates", "customer_portal", "portal_dashboard.html")
DEST = os.path.join(ROOT, "customer_portal", "templates", "customer_portal", "portal_dashboard")

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

print("Extracting portal_dashboard partials...")

write_partial("_styles.html", 21, 624, "Styles")
write_partial("_navbar.html", 630, 648, "Navbar")
write_partial("_hero.html", 650, 682, "Hero Section")
write_partial("_alerts.html", 684, 706, "Alerts")
write_partial("_left_column.html", 711, 920, "Left Column")
write_partial("_right_column.html", 922, 1030, "Right Column")
write_partial("_footer.html", 1034, 1036, "Footer")
write_partial("_modals.html", 1038, 1235, "Modals")
write_partial("_scripts.html", 1237, len(lines)-3, "Scripts") # Exclude </body> </html>

orchestrator = r'''{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Portal – Gametech Unli Fiber</title>
    <meta name="description" content="Manage your Gametech Unli Fiber subscription, view your connection status, and pay your bills.">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <script>
        // Apply theme immediately to prevent flash
        (function() {
            const theme = localStorage.getItem('gt-portal-theme') || 'dark';
            document.documentElement.setAttribute('data-theme', theme);
        })();
    </script>
    <style>
        {% include "customer_portal/portal_dashboard/_styles.html" %}
    </style>
    <!-- PWA Manifest -->
    <link rel="manifest" href="{% static 'manifest.json' %}">
</head>
<body>

{% include "customer_portal/portal_dashboard/_navbar.html" %}
{% include "customer_portal/portal_dashboard/_hero.html" %}
{% include "customer_portal/portal_dashboard/_alerts.html" %}

<!-- MAIN GRID -->
<div class="p-main">
    {% include "customer_portal/portal_dashboard/_left_column.html" %}
    {% include "customer_portal/portal_dashboard/_right_column.html" %}
</div>

{% include "customer_portal/portal_dashboard/_footer.html" %}
{% include "customer_portal/portal_dashboard/_modals.html" %}
{% include "customer_portal/portal_dashboard/_scripts.html" %}

</body>
</html>
'''

with open(SRC, "w", encoding="utf-8") as f:
    f.write(orchestrator)

print(f"Rewrote portal_dashboard.html as orchestrator ({len(orchestrator.splitlines())} lines)")
