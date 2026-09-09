"""Deep audit: analyze the structure of the worst offender files."""
import re
import os

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"

def audit_html(filepath, label):
    with open(os.path.join(ROOT, filepath), encoding='utf-8', errors='replace') as f:
        content = f.read()
    lines = content.split('\n')
    print(f"\n{'='*80}")
    print(f"  {label} ({len(lines)} lines, {len(content)//1024} KB)")
    print(f"{'='*80}")

    # Script blocks
    scripts = re.findall(r'<script.*?</script>', content, re.DOTALL)
    script_lines = sum(s.count('\n') for s in scripts)
    print(f"  <script> blocks: {len(scripts)}, total ~{script_lines} lines of JS")

    # Style blocks
    styles = re.findall(r'<style.*?</style>', content, re.DOTALL)
    style_lines = sum(s.count('\n') for s in styles)
    print(f"  <style> blocks: {len(styles)}, total ~{style_lines} lines of CSS")

    # Modals
    modals = re.findall(r'id="(\w*[Mm]odal\w*)"', content)
    print(f"  Modals: {len(modals)}")
    for m in modals:
        print(f"    - #{m}")

    # HTML sections (via comments)
    comments = re.findall(r'<!--\s*(.+?)\s*-->', content)
    if comments:
        print(f"  Comment-delimited sections ({len(comments)}):")
        for c in comments[:25]:
            print(f"    - {c[:80].encode('ascii', 'replace').decode()}")

    # Block tags
    blocks = re.findall(r'{%\s*block\s+(\w+)\s*%}', content)
    if blocks:
        print(f"  Template blocks: {blocks}")

    # Include tags
    includes = re.findall(r'{%\s*include\s+[\'\"](.*?)[\'\"]', content)
    if includes:
        print(f"  Includes: {includes}")

    return script_lines, style_lines, len(modals)

def audit_python(filepath, label):
    with open(os.path.join(ROOT, filepath), encoding='utf-8', errors='replace') as f:
        content = f.read()
    lines = content.split('\n')
    print(f"\n{'='*80}")
    print(f"  {label} ({len(lines)} lines, {len(content)//1024} KB)")
    print(f"{'='*80}")

    # Functions/classes
    funcs = re.findall(r'^(?:def|class)\s+(\w+)', content, re.MULTILINE)
    print(f"  Functions/classes: {len(funcs)}")
    for f in funcs:
        print(f"    - {f}")

# ---- AUDIT THE BIG FILES ----

audit_html(r"billing\templates\billing\dashboard.html", "dashboard.html")
audit_html(r"billing\templates\billing\base.html", "base.html")
audit_html(r"billing\templates\billing\live_monitoring.html", "live_monitoring.html")
audit_html(r"billing\templates\billing\view_customer.html", "view_customer.html")
audit_html(r"billing\templates\billing\customer_list.html", "customer_list.html")
audit_html(r"billing\templates\billing\changelog.html", "changelog.html")
audit_html(r"customer_portal\templates\customer_portal\portal_dashboard.html", "portal_dashboard.html")

print("\n\n" + "="*80)
print("  PYTHON FILES AUDIT")
print("="*80)

audit_python(r"billing\views\customers.py", "views/customers.py")
audit_python(r"billing\views\payments.py", "views/payments.py")
audit_python(r"billing\views\api.py", "views/api.py")
audit_python(r"billing\models.py", "models.py")
audit_python(r"billing\views\services.py", "views/services.py")
audit_python(r"billing\views\settings.py", "views/settings.py")
audit_python(r"billing\views\auth.py", "views/auth.py")
audit_python(r"billing\signals.py", "signals.py")
audit_python(r"billing\tasks.py", "tasks.py")
audit_python(r"network_manager\views.py", "network_manager/views.py")
audit_python(r"network_manager\services.py", "network_manager/services.py")

# ---- CSS FILES ----
print("\n\n" + "="*80)
print("  CSS FILES AUDIT")
print("="*80)
for cssfile in [r"static\css\theme.css", r"static\css\styles.css"]:
    fp = os.path.join(ROOT, cssfile)
    if os.path.exists(fp):
        with open(fp, encoding='utf-8', errors='replace') as f:
            content = f.read()
        lines = content.split('\n')
        # Count comment sections
        sections = re.findall(r'/\*[\s=*-]*(.+?)[\s=*-]*\*/', content)
        print(f"\n  {cssfile} ({len(lines)} lines, {len(content)//1024} KB)")
        print(f"    Comment sections: {len(sections)}")
        for s in sections[:15]:
            print(f"      - {s.strip()[:70]}")

# ---- PARTIALS ----
print("\n\n" + "="*80)
print("  EXISTING PARTIALS (template includes already being used)")
print("="*80)
partials_dir = os.path.join(ROOT, "billing", "templates", "billing", "partials")
if os.path.isdir(partials_dir):
    for fn in os.listdir(partials_dir):
        fp = os.path.join(partials_dir, fn)
        with open(fp, encoding='utf-8', errors='replace') as f:
            lines = sum(1 for _ in f)
        print(f"  {fn} ({lines} lines)")
else:
    print("  No partials directory found")
