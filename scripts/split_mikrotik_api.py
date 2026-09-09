import os
import ast
import shutil

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"
SRC = os.path.join(ROOT, "network_manager", "services.py")
DEST_DIR = os.path.join(ROOT, "network_manager", "services")

if os.path.exists(DEST_DIR):
    shutil.rmtree(DEST_DIR)
os.makedirs(DEST_DIR, exist_ok=True)

with open(SRC, encoding="utf-8") as f:
    source_code = f.read()
    lines = source_code.splitlines()

tree = ast.parse(source_code)

imports = []
methods = {}

for node in tree.body:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        start = node.lineno - 1
        end = node.end_lineno
        imports.append("\n".join(lines[start:end]))
    elif isinstance(node, ast.ClassDef) and node.name == 'MikrotikAPI':
        for method_node in node.body:
            if isinstance(method_node, ast.FunctionDef):
                start = method_node.lineno - 1
                end = method_node.end_lineno
                if method_node.decorator_list:
                    start = method_node.decorator_list[0].lineno - 1
                methods[method_node.name] = "\n".join(lines[start:end])

mapping = {
    'base.py': {
        'class_name': 'MikrotikBase',
        'methods': ['__init__', '_get_api']
    },
    'users.py': {
        'class_name': 'MikrotikUsersMixin',
        'methods': ['get_active_pppoe_users', 'set_pppoe_comment', 'remove_active_pppoe_user', 'kick_active_user', 'set_user_pppoe_profile', 'suspend_pppoe_user', 'enable_pppoe_user', 'delete_pppoe_user', 'add_pppoe_user']
    },
    'profiles.py': {
        'class_name': 'MikrotikProfilesMixin',
        'methods': ['get_ppp_profiles', 'delete_ppp_profile', 'add_ppp_profile', 'update_ppp_profile', 'sync_plan_to_mikrotik', 'delete_plan_from_mikrotik']
    },
    'secrets.py': {
        'class_name': 'MikrotikSecretsMixin',
        'methods': ['get_ppp_secrets', 'delete_ppp_secret', 'update_ppp_secret']
    },
    'system.py': {
        'class_name': 'MikrotikSystemMixin',
        'methods': ['get_system_resources', 'get_optical_readings', 'get_simple_queues', 'get_interfaces_traffic']
    }
}

imports_text = "\n".join(imports) + "\n\n"
imports_text += "logger = logging.getLogger(__name__)\n\n"

for filename, data in mapping.items():
    filepath = os.path.join(DEST_DIR, filename)
    class_name = data['class_name']
    func_names = data['methods']
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(imports_text)
        f.write(f"class {class_name}:\n")
        
        has_methods = False
        for name in func_names:
            if name in methods:
                has_methods = True
                # Indent method 4 spaces
                method_code = methods[name]
                indented_code = "\n".join(["    " + line if line else "" for line in method_code.split("\n")])
                f.write(indented_code + "\n\n")
        
        if not has_methods:
            f.write("    pass\n")

    print(f"Created {filename} with class {class_name}")

init_path = os.path.join(DEST_DIR, "__init__.py")
with open(init_path, "w", encoding="utf-8") as f:
    for data in mapping.values():
        module_name = [k for k, v in mapping.items() if v == data][0].replace(".py", "")
        f.write(f"from .{module_name} import {data['class_name']}\n")
    
    f.write("\n")
    f.write(f"class MikrotikAPI(MikrotikBase, MikrotikUsersMixin, MikrotikProfilesMixin, MikrotikSecretsMixin, MikrotikSystemMixin):\n")
    f.write(f"    pass\n")

print("Created __init__.py")

os.remove(SRC)
print(f"Removed original {SRC}")
