"""Quick audit: count lines in all source files."""
import os

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"
SKIP = {'venv', '__pycache__', 'staticfiles', 'migrations', '.git',
        'node_modules', 'Dispatch Monitoring System', 'docs', '.github'}
EXTS = {'.html', '.py', '.css', '.js'}

results = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in SKIP]
    for fn in filenames:
        ext = os.path.splitext(fn)[1].lower()
        if ext in EXTS:
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, encoding='utf-8', errors='replace') as f:
                    lines = sum(1 for _ in f)
                size_kb = round(os.path.getsize(fp) / 1024, 1)
                rel = os.path.relpath(fp, ROOT)
                results.append((lines, size_kb, rel))
            except:
                pass

results.sort(key=lambda x: x[0], reverse=True)
print(f"{'LINES':>6}  {'KB':>8}  FILE")
print("-" * 80)
for lines, kb, path in results[:50]:
    print(f"{lines:>6}  {kb:>8}  {path}")
print(f"\n--- Total files scanned: {len(results)} ---")
print(f"--- Files over 500 lines: {sum(1 for l,_,_ in results if l > 500)} ---")
print(f"--- Files over 1000 lines: {sum(1 for l,_,_ in results if l > 1000)} ---")
