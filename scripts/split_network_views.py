import os
import ast
import shutil

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"
SRC = os.path.join(ROOT, "network_manager", "views.py")
DEST_DIR = os.path.join(ROOT, "network_manager", "views")

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
    'devices.py': ['device_list', 'add_device', 'edit_device', 'delete_device', 'test_device_connection', 'sync_device_users', 'device_hardware_api', 'setup_router_profiles'],
    'naps.py': ['nap_list_view', 'add_nap_view', 'edit_nap_view', 'delete_nap_view'],
    'tools.py': ['fbt_plc_calculator_view'],
    'sync.py': ['sync_manager', 'sync_push_user', 'sync_autofix_user', 'sync_delete_user', 'sync_bulk_action'],
    'winbox.py': ['winbox_routers', 'winbox_dashboard', 'winbox_secret_action', 'winbox_profile_action', 'winbox_kick_action']
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
