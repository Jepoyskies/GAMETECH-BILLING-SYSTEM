import os

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"
SRC = os.path.join(ROOT, "billing", "templates", "billing", "customer_list.html")
DEST = os.path.join(ROOT, "billing", "templates", "billing", "customer_list")

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

print("Extracting customer_list partials...")

write_partial("_styles.html", 9, 118, "Styles")
write_partial("_hero.html", 136, 175, "Hero & Top Actions")
write_partial("_filters.html", 178, 194, "Filters")
write_partial("_table.html", 196, 352, "Customer Table")
write_partial("_modals.html", 358, 439, "Bulk Modals")
write_partial("_scripts.html", 445, len(lines)-1, "Scripts")

orchestrator = r'''{% extends "billing/base.html" %}
{% load static %}

{% block title %}Customers{% endblock %}

{% block extra_css %}
{% include "billing/customer_list/_styles.html" %}
{% endblock %}

{% block content %}
<main class="container-fluid py-4 px-3 px-md-4">
    <!-- Messages / Notifications -->
    {% if messages %}
    {% for message in messages %}
    <div class="alert alert-{{ message.tags }} alert-dismissible fade show shadow-sm" role="alert">
        {{ message }}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>
    {% endfor %}
    {% endif %}

    {% include "billing/customer_list/_hero.html" %}
    {% include "billing/customer_list/_filters.html" %}
    {% include "billing/customer_list/_table.html" %}
</main>

{% include "billing/customer_list/_modals.html" %}
{% endblock %}

{% block extra_js %}
{% include "billing/customer_list/_scripts.html" %}
{% endblock %}
'''

with open(SRC, "w", encoding="utf-8") as f:
    f.write(orchestrator)

print(f"Rewrote customer_list.html as orchestrator ({len(orchestrator.splitlines())} lines)")
