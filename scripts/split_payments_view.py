import os
import ast
import shutil

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"
SRC = os.path.join(ROOT, "billing", "views", "payments.py")
DEST_DIR = os.path.join(ROOT, "billing", "views", "payments")

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
    'logs.py': ['payment_logs_view', 'rebates_logs_view', 'payment_addon_logs_view'],
    'transactions.py': ['create_payment_view', 'pay_customer_view', 'payment_portal_view', 'payment_success_view'],
    'rebates.py': ['customer_rebate_view', 'customer_rollback_view'],
    'management.py': ['edit_payment_log_view', 'revert_transfer_payment']
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

