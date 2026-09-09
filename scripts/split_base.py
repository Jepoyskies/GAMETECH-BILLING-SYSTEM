import os

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"
SRC = os.path.join(ROOT, "billing", "templates", "billing", "base.html")
DEST = os.path.join(ROOT, "billing", "templates", "billing", "base")

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

print("Extracting base partials...")

# 1. Styles (Lines 14-241, 251-261) -> we can just take lines 14-241 for main styles, and 251-261 for pulse styles. Let's merge them into _base_styles.html
content_styles = "".join(lines[13:241]) + "".join(lines[250:261])
with open(os.path.join(DEST, "_styles.html"), "w", encoding="utf-8") as f:
    f.write("<!-- Base Partial: Styles -->\n" + content_styles)

# 2. Sidebar (Lines 264-362)
write_partial("_sidebar.html", 264, 362, "Sidebar")

# 3. Topbar (Lines 367-639)
write_partial("_topbar.html", 367, 639, "Topbar")

# 4. Scripts (Lines 647-1065) -> Includes the improvement modal html, maybe separate that?
# Let's extract the improvement modal separately.
write_partial("_improvement_modal.html", 960, 992, "Improvement Request Modal")

# The rest of scripts: 647-958 and 994-1065
content_scripts = "".join(lines[646:958]) + "".join(lines[993:1065])
with open(os.path.join(DEST, "_scripts.html"), "w", encoding="utf-8") as f:
    f.write("<!-- Base Partial: Scripts -->\n" + content_scripts)

# New orchestrator base.html
orchestrator = r'''{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Gametech Unli Fiber{% endblock %}</title>
    <!-- CSS Links -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Montserrat:wght@400;500;600&family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    
    {% include "billing/base/_styles.html" %}
    <link rel="stylesheet" href="{% static 'css/theme.css' %}?v=2.1">
    {% block extra_css %}{% endblock %}
    
    <script>
        // Check and apply theme immediately to prevent flash
        if (localStorage.getItem('theme') === 'dark') {
            document.documentElement.classList.add('dark-mode');
        }
    </script>
</head>
<body class="bg-light">

{% include "billing/base/_sidebar.html" %}

<div class="sidebar-overlay" id="sidebarOverlay"></div>

<div class="main-content" id="mainContent">
    {% include "billing/base/_topbar.html" %}

    <main class="content-wrapper p-3">
        {% block content %}
        {% endblock %}
    </main>
</div>

{% include "billing/base/_improvement_modal.html" %}

{% include "billing/base/_scripts.html" %}
{% block extra_js %}{% endblock %}
</body>
</html>
'''

with open(SRC, "w", encoding="utf-8") as f:
    f.write(orchestrator)

print(f"Rewrote base.html as orchestrator ({len(orchestrator.splitlines())} lines)")
