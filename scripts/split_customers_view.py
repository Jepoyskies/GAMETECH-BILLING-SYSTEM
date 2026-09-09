import os
import ast
import shutil

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"
SRC = os.path.join(ROOT, "billing", "views", "customers.py")
DEST_DIR = os.path.join(ROOT, "billing", "views", "customers")

if os.path.exists(DEST_DIR):
    shutil.rmtree(DEST_DIR)
os.makedirs(DEST_DIR, exist_ok=True)

with open(SRC, encoding="utf-8") as f:
    source_code = f.read()
    lines = source_code.splitlines()

tree = ast.parse(source_code)

# We need to preserve imports at the top
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
        # Decorators are part of the function definition
        if node.decorator_list:
            start = node.decorator_list[0].lineno - 1
        functions[node.name] = "\n".join(lines[start:end])

# Define how to split functions
mapping = {
    'list.py': ['customer_list', 'mac_history_view'],
    'crud.py': ['add_customer', 'edit_customer', 'view_customer', 'delete_customer'],
    'actions.py': [
        'customer_force_suspend', 'customer_kick_session', 'customer_force_reactivate',
        'edit_customer_expiration', 'edit_customer_balance', 'statement_of_account_view',
        'bulk_transfer_router', 'verify_customer', 'unverify_customer'
    ],
    'messaging.py': ['bulk_sms_view', 'bulk_email_view', 'sms_view'],
    'tasks.py': ['auto_suspend_view']
}

imports_text = "\n".join(imports) + "\n\n"
# Also need to import __init__ stuff maybe? 
# The original customers.py had its own imports. Let's just put all original imports in each file for simplicity.

for filename, func_names in mapping.items():
    filepath = os.path.join(DEST_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(imports_text)
        for name in func_names:
            if name in functions:
                f.write(functions[name] + "\n\n")
    print(f"Created {filename} with functions: {', '.join(func_names)}")

# Create __init__.py
init_path = os.path.join(DEST_DIR, "__init__.py")
with open(init_path, "w", encoding="utf-8") as f:
    for filename in mapping.keys():
        module_name = filename.replace(".py", "")
        f.write(f"from .{module_name} import *\n")

print("Created __init__.py")

# Optionally remove the original
os.remove(SRC)
print(f"Removed original {SRC}")

