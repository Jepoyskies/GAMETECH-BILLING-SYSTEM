# COMMON_TASKS.md — Quick-Reference Recipes

> **PURPOSE**: Copy-paste-ready recipes for the most common tasks. No exploration needed.

---

## 1. Add a New Settings/Admin Card

```html
<div class="col-6 col-sm-4 col-lg-3 col-xl-2">
  <a href="{% url 'your_url_name' %}" class="settings-nav-card">
    <div class="snc-icon" style="background:rgba(59,130,246,0.12);color:#2563eb;"><i class="fas fa-icon-name"></i></div>
    <div class="snc-title">Card Title</div>
    <div class="snc-desc">Short description</div>
    <span class="snc-badge" style="background:#2563eb;"><i class="fas fa-arrow-right"></i> Open</span>
  </a>
</div>
```

**Deploy**: `git add -A; git commit -m "feat: add card"; git push origin main; ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git pull origin main"; ssh root@143.198.207.144 "docker restart gametech-web"`

---

## 2. Add a New Sidebar Menu Item

```html
{% if request.user.role_perms.subtabs.your_module %}
<li>
  <a href="#yourSubmenu" data-bs-toggle="collapse" aria-expanded="false" class="menu-link dropdown-toggle">
    <span class="icon"><i class="fas fa-icon"></i></span> <span>Menu Label</span>
  </a>
  <ul class="collapse list-unstyled" id="yourSubmenu" data-bs-parent="#sidebarNav">
    <li><a href="{% url 'your_url' %}" class="menu-link sub-menu-link"><span>Sub Item</span></a></li>
  </ul>
</li>
{% endif %}
```

**Also register in**: `billing/models.py` (`subtab_specs`) AND `billing/views/staff.py` (`ROLE_MODULE_SPECS`)

---

## 3. Add a New API Endpoint

```python
# billing/urls.py
path("api/v1/<resource>/", views.your_view, name="api_your_resource"),

# billing/views/api/<domain>.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def your_view(request):
    if request.method == "GET":
        data = {"key": "value"}
        return JsonResponse(data)
    return JsonResponse({"error": "Method not allowed"}, status=405)
```

---

## 4. Add a New Model Field

```python
# 1. Add to model
field_name = models.CharField(max_length=100, default="default_value")

# 2. Create migration locally
python manage.py makemigrations billing --name add_field_name

# 3. Commit migration file IN THE SAME COMMIT as model change
git add billing/models.py billing/migrations/00XX_add_field_name.py
git commit -m "feat: add field_name to Model"

# 4. Deploy
git push origin main
ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git pull origin main"
ssh root@143.198.207.144 "docker exec gametech-web python manage.py migrate"
ssh root@143.198.207.144 "docker restart gametech-web"
```

---

## 5. Fix a 500 Error

```bash
# Step 1: Get the traceback
ssh root@143.198.207.144 "docker logs --since 2m gametech-web 2>&1 | tail -40"

# Step 2: Read ONLY the file:line from the traceback (50-80 lines max)

# Step 3: Fix the exact line, then deploy
```

---

## 6. Fix a Template (Modal/Card/Page)

```bash
# Step 1: Find the partial
grep "partial_name" gametech_filing_index.md

# Step 2: Check div balance
'content = open("path/to/_partial.html", "r", encoding="utf-8").read(); import re; o = len(re.findall(r"<div\b", content)); c = len(re.findall(r"</div>", content)); print(f"diff: {o-c}")' | python -

# Step 3: Fix, verify include chain, deploy
```

---

## 7. Add a New Page

```python
# 1. URL
path("your-path/", views.your_view, name="your_page"),

# 2. View (in appropriate views/ file)
@login_required
def your_view(request):
    return render(request, "billing/your_page.html", context)

# 3. Template (orchestrator pattern)
{% extends "billing/base.html" %}
{% block content %}
  <!-- Include partials -->
  {% include "billing/your_page/_hero.html" %}
  {% include "billing/your_page/_content.html" %}
{% endblock %}

# 4. Sidebar link (see recipe #2)

# 5. Settings/Admin card (see recipe #1)
```

---

## 8. Fix CSS/Dark Mode Issue

```bash
# Step 1: Identify the exact selector causing the issue
# Step 2: Check if it's in the right partial (_styles.html or inline <style>)
# Step 3: Use design tokens (var(--surface-card), var(--text-primary), etc.)
# Step 4: Test both light and dark mode
# Step 5: If static file changed, run collectstatic
ssh root@143.198.207.144 "docker exec gametech-web python manage.py collectstatic --noinput"
```

---

## 9. Fix a Permission/403 Error

```python
# Check the view's decorator
@role_required(["Admin"])  # ← What roles are allowed?

# Check the user's role
# In sidebar: {% if request.user.role_perms.subtabs.your_module %}

# Fix: Either change the decorator or grant the user the right role/permission
```

---

## 10. Fix a Cache/Zombie Data Issue

```bash
# Step 1: Check Redis
ssh root@143.198.207.144 "docker exec gametech-redis redis-cli KEYS 'pattern*'"
ssh root@143.198.207.144 "docker exec gametech-redis redis-cli GET 'key_name'"

# Step 2: Find the cache key in AGENTS.md Rule #23 Registry

# Step 3: Fix the view that should invalidate the cache
# Add: cache.delete("key_name") or cache.set("key_name", new_value)
```

---

## 11. Add a Background Task

```python
# billing/tasks.py
from celery import shared_task

@shared_task
def your_task():
    # Your logic here
    pass

# Schedule in gametech_core/settings.py CELERY_BEAT_SCHEDULE
# Or call from a view: your_task.delay()
```

---

## 12. Fix a Migration Conflict

```bash
# NEVER run makemigrations on the droplet
# Fix locally:
python manage.py makemigrations --merge
git add billing/migrations/
git commit -m "fix: merge migrations"
git push origin main
ssh root@143.198.207.144 "cd /root/GAMETECH-BILLING-SYSTEM && git pull origin main"
ssh root@143.198.207.144 "docker exec gametech-web python manage.py migrate"
```
