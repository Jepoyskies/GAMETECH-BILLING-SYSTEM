import os

ROOT = r"c:\Users\alber\OneDrive\Documents\Vscode\GAMETECH-BILLING-SYSTEM"
SRC = os.path.join(ROOT, "static", "css", "theme.css")
DEST_DIR = os.path.join(ROOT, "static", "css", "theme")

os.makedirs(DEST_DIR, exist_ok=True)

with open(SRC, encoding="utf-8") as f:
    lines = f.readlines()

def write_css(filename, start_line, end_line):
    content = "".join(lines[start_line:end_line])
    filepath = os.path.join(DEST_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created {filename} with {end_line - start_line} lines")

write_css("tokens_and_base.css", 0, 1164)
write_css("layout_and_darkmode.css", 1164, 2008)
write_css("components.css", 2008, len(lines))

with open(SRC, "w", encoding="utf-8") as f:
    f.write('@import url("theme/tokens_and_base.css");\n')
    f.write('@import url("theme/layout_and_darkmode.css");\n')
    f.write('@import url("theme/components.css");\n')

print("Rewrote theme.css to use @import")
