from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def format_log_details(log):
    sentences = []
    old_data = str(log.old_data).strip() if log.old_data else ""
    new_data = str(log.new_data).strip() if log.new_data else ""
    action = str(log.action).upper()
    
    # Clean up 'null' strings
    if old_data == 'null': old_data = ""
    if new_data == 'null': new_data = ""

    # Case 1: Profile update with -> or → (arrow format)
    if '→' in old_data or '->' in old_data:
        lines = old_data.split('\n')
        for line in lines:
            line = line.strip()
            if not line: continue
            
            if '→' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    change = parts[1]
                    if '→' in change:
                        old_val, new_val = change.split('→', 1)
                        sentences.append(f"Changed <strong>{key}</strong> from <span class='text-danger'>{old_val.strip()}</span> to <span class='text-success'>{new_val.strip()}</span>.")
            elif '->' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    change = parts[1]
                    if '->' in change:
                        old_val, new_val = change.split('->', 1)
                        sentences.append(f"Changed <strong>{key}</strong> from <span class='text-danger'>{old_val.strip()}</span> to <span class='text-success'>{new_val.strip()}</span>.")
                        
    # Case 2: Deletion
    elif action == 'DELETE' and old_data:
        lines = old_data.split('\n')
        for line in lines:
            if ':' in line:
                key, val = line.split(':', 1)
                sentences.append(f"<strong>{key.strip()}</strong> was {val.strip()}.")
            elif line.strip():
                sentences.append(line.strip())
                
    # Case 3: Addition
    elif action == 'ADD' and new_data:
        lines = new_data.split('\n')
        for line in lines:
            if ':' in line:
                key, val = line.split(':', 1)
                sentences.append(f"Set <strong>{key.strip()}</strong> to <span class='text-success'>{val.strip()}</span>.")
            elif line.strip():
                sentences.append(line.strip())
                
    # Case 4: Key-value Updates (no arrows)
    elif 'UPDATE' in action and old_data and new_data:
        old_dict = {}
        for line in old_data.split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                old_dict[k.strip()] = v.strip()
                
        new_dict = {}
        for line in new_data.split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                new_dict[k.strip()] = v.strip()
                
        for key, new_val in new_dict.items():
            old_val = old_dict.get(key)
            if old_val and old_val != new_val:
                sentences.append(f"Changed <strong>{key}</strong> from <span class='text-danger'>{old_val}</span> to <span class='text-success'>{new_val}</span>.")
            elif not old_val:
                sentences.append(f"Set <strong>{key}</strong> to <span class='text-success'>{new_val}</span>.")
                
        for key, old_val in old_dict.items():
            if key not in new_dict:
                sentences.append(f"Removed <strong>{key}</strong> (was <span class='text-danger'>{old_val}</span>).")

    # Fallback
    if not sentences:
        if new_data and new_data != 'None' and 'Profile updated via UI' not in new_data:
            sentences.append(f"{new_data}")
        elif old_data and old_data != 'None':
            sentences.append(f"{old_data}")
            
    if not sentences:
        return mark_safe("<span class='text-muted fst-italic'>No additional comments</span>")

    # Build HTML list
    html = "<ul class='mb-0 ps-3' style='font-size: 0.85rem; color: #475569;'>"
    for s in sentences:
        html += f"<li class='mb-1'>{s}</li>"
    html += "</ul>"
    
    return mark_safe(html)
