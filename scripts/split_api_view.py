import os
import ast
import shutil

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"
SRC = os.path.join(ROOT, "billing", "views", "api.py")
DEST_DIR = os.path.join(ROOT, "billing", "views", "api")

if os.path.exists(DEST_DIR):
    shutil.rmtree(DEST_DIR)
os.makedirs(DEST_DIR, exist_ok=True)

with open(SRC, encoding="utf-8") as f:
    source_code = f.read()
    lines = source_code.splitlines()

tree = ast.parse(source_code)

imports = []
functions = {}

for node in tree.body:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        start = node.lineno - 1
        end = node.end_lineno
        imports.append("\n".join(lines[start:end]))
    elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        start = node.lineno - 1
        end = node.end_lineno
        if node.decorator_list:
            start = node.decorator_list[0].lineno - 1
        functions[node.name] = "\n".join(lines[start:end])

mapping = {
    'network.py': ['mikrotik_active_users_data_api', 'api_offline_users', 'api_router_uplink', 'api_customer_mikrotik_status', 'api_network_alerts', 'api_active_pppoe_usernames', 'api_downdetector_data'],
    'dashboard.py': ['api_live_monitoring_data', 'subscription_plans_data_api', 'api_top_clients', 'api_popular_plans'],
    'notifications.py': ['notifications_list_view', 'api_notifications', 'api_mark_notification_read', 'api_mark_all_notifications_read'],
    'addons.py': ['live_addon_requests_api', 'resolve_addon_request_api']
}

imports_text = "\n".join(imports) + "\n\n"

for filename, func_names in mapping.items():
    filepath = os.path.join(DEST_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(imports_text)
        for name in func_names:
            if name in functions:
                f.write(functions[name] + "\n\n")
    print(f"Created {filename} with functions: {', '.join(func_names)}")

init_path = os.path.join(DEST_DIR, "__init__.py")
with open(init_path, "w", encoding="utf-8") as f:
    for filename in mapping.keys():
        module_name = filename.replace(".py", "")
        f.write(f"from .{module_name} import *\n")

print("Created __init__.py")

os.remove(SRC)
print(f"Removed original {SRC}")
