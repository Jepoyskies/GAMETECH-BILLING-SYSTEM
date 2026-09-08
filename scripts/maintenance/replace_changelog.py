import re

file_path = r"C:\Users\gametech\Documents\GAMETECH-BILLING-SYSTEM\billing\templates\billing\base.html"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

with open('scratch_changelog.html', 'r', encoding='utf-8') as f:
    new_changelog = f.read()

# The dropdown-menu div starts around line 376. We need to replace everything inside it.
pattern = re.compile(r'(<div class="dropdown-menu dropdown-menu-end shadow-lg border-0"[^>]+>)\s*<!-- Header -->.*?</div>\s*</div>\s*<!-- Changelog End -->', re.DOTALL)

if pattern.search(content):
    pass # Wait, we don't have "<!-- Changelog End -->" in base.html
