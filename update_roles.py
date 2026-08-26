import re

# Update billing/views.py
with open('billing/views.py', 'r') as f:
    b_content = f.read()

def b_replacer(match):
    decorator = match.group(1)
    func_def = match.group(2)
    if 'agent' in func_def or 'staff' in func_def:
        return decorator + '\n' + func_def
    else:
        new_dec = decorator.replace("['Admin', 'Editor']", "['Admin', 'Editor', 'CSR']")
        return new_dec + '\n' + func_def

b_content = re.sub(r'(@role_required\(\[.*?\]\))\s*\n*(.*?def [a-zA-Z0-9_]+)', b_replacer, b_content)
with open('billing/views.py', 'w') as f:
    f.write(b_content)

# Update network_manager/views.py
with open('network_manager/views.py', 'r') as f:
    n_content = f.read()

def n_replacer(match):
    decorator = match.group(1)
    func_def = match.group(2)
    new_dec = decorator.replace("['Admin', 'Editor']", "['Admin', 'Editor', 'CSR']").replace("['Admin']", "['Admin', 'CSR']")
    return new_dec + '\n' + func_def

n_content = re.sub(r'(@role_required\(\[.*?\]\))\s*\n*(.*?def [a-zA-Z0-9_]+)', n_replacer, n_content)
with open('network_manager/views.py', 'w') as f:
    f.write(n_content)

# Update base.html
with open('billing/templates/billing/base.html', 'r') as f:
    html = f.read()

html = html.replace("{% if request.user.role == 'Admin' or request.user.role == 'Technician' %}", "{% if request.user.role in 'Admin,Technician,CSR' %}")

with open('billing/templates/billing/base.html', 'w') as f:
    f.write(html)
print('Done!')
