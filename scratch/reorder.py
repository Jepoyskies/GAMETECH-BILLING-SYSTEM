import sys

filepath = r"c:\JILLIAN BOC\ANTIGRAVITY\GAMETECH-BILLING-SYSTEM\billing\templates\billing\base.html"
with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

cta_block = lines[310:320] # 311-319
bell_block = lines[320:358] # 321-358 (wait, let's check line 358)
online_block = lines[358:389] 
changelog_block = lines[389:513] 
theme_block = lines[513:521] 

divider = ['\n', '            <!-- Subtle Vertical Divider -->\n', '            <div class="vr mx-2" style="background-color: #d1d5db; width: 1.5px;"></div>\n', '\n']

new_order = cta_block + theme_block + divider + changelog_block + online_block + bell_block

new_lines = lines[:310] + new_order + lines[521:]

for i in range(len(new_lines)):
    if 'id="profileDropdown"' in new_lines[i]:
        if 'btn btn-sm' in new_lines[i] and 'ms-2' not in new_lines[i]:
            new_lines[i] = new_lines[i].replace('btn btn-sm', 'btn btn-sm ms-2')
        break

with open(filepath, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Done")
