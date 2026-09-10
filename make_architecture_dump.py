import os

# Essential architecture files that define data models, routes, tasks, and system contracts
ARCHITECTURE_FILES = [
    'gametech_core/settings.py',
    'gametech_core/urls.py',
    'billing/models.py',
    'billing/urls.py',
    'billing/tasks.py',
    'billing/utils.py',
    'network_manager/models.py',
    'network_manager/urls.py',
    'network_manager/services/base.py',
    'network_manager/sync_services.py',
    'customer_portal/models.py',
    'customer_portal/urls.py',
    'dispatch/models.py',
    'dispatch/urls.py',
]

OUTPUT_FILE = 'gametech_architecture_map.txt'

def create_architecture_dump():
    total_lines = 0
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
        outfile.write("=" * 70 + "\n")
        outfile.write("GAMETECH UNLI FIBER - CORE SYSTEM ARCHITECTURE & SCHEMA MAP\n")
        outfile.write("=" * 70 + "\n\n")
        outfile.write("This lean blueprint contains all Database Models, URL Routes, Celery Tasks,\n")
        outfile.write("and Core Hardware Bridge services (~2,000 lines / ~8,500 tokens).\n\n")

        for relative_path in ARCHITECTURE_FILES:
            norm_path = os.path.normpath(relative_path)
            if os.path.exists(norm_path):
                with open(norm_path, 'r', encoding='utf-8', errors='ignore') as infile:
                    lines = infile.readlines()
                    total_lines += len(lines)
                    outfile.write(f"\n{'#'*60}\n")
                    outfile.write(f"### FILE: {relative_path} ({len(lines)} lines)\n")
                    outfile.write(f"{'#'*60}\n\n")
                    outfile.writelines(lines)
                    outfile.write("\n")
            else:
                print(f"Warning: {relative_path} not found")

    print(f"Done! Created {OUTPUT_FILE} ({total_lines} lines).")

if __name__ == '__main__':
    create_architecture_dump()
