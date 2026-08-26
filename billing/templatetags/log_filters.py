from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def format_log_details(log):
    sentences = []
    old_data = str(log.old_data).strip() if log.old_data else ""
    new_data = str(log.new_data).strip() if log.new_data else ""
    action = str(log.action).upper()
    
    if old_data == 'null': old_data = ""
    if new_data == 'null': new_data = ""
    
    bg_class = "bg-danger-subtle text-danger" if action == 'DELETE' else "bg-light text-dark"
    border_class = "border-danger-subtle" if action == 'DELETE' else "border-light"
    
    html = f"<div class='p-3 rounded-3 {bg_class} {border_class} border' style='font-size: 0.85rem; font-family: Inter, sans-serif;'>"
    html += "<table class='table table-sm table-borderless mb-0' style='background: transparent;'>"
    html += "<tbody>"

    # Action: DELETE
    if action == 'DELETE' and old_data:
        parts = {}
        for line in old_data.split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                parts[k.strip()] = v.strip().replace("'", "")
        
        if 'Amount' in parts:
            amt = parts.get('Amount', '')
            method = parts.get('Method', '')
            ref = parts.get('Reference', '')
            html += f"<tr><td class='text-danger p-0 fw-medium'><i class='fas fa-exclamation-triangle me-2'></i> Deleted {method} Payment of ₱{amt} (Ref: {ref})</td></tr>"
        else:
            for k, v in parts.items():
                html += f"<tr><td class='p-0 text-danger fw-semibold' style='width: 120px;'>{k}:</td><td class='p-0 text-danger'>{v}</td></tr>"

    # Action: ADD / UPDATE
    else:
        # Case 1: Profile update with -> or → (arrow format)
        if '→' in old_data or '->' in old_data:
            lines = old_data.split('\n')
            for line in lines:
                line = line.strip()
                if not line: continue
                if '→' in line or '->' in line:
                    sep = '→' if '→' in line else '->'
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        old_val, new_val = parts[1].split(sep, 1)
                        old_val = old_val.strip().replace("'", "")
                        new_val = new_val.strip().replace("'", "")
                        html += f"<tr><td class='p-1 fw-semibold text-muted' style='width: 100px;'>{key}:</td><td class='p-1'><span class='text-muted text-decoration-line-through me-2'>{old_val}</span> <i class='fas fa-arrow-right text-muted mx-2' style='font-size: 0.7rem;'></i> <span class='text-success fw-medium'>{new_val}</span></td></tr>"
        
        # Case 2: Key-value Updates (no arrows)
        elif 'UPDATE' in action and old_data and new_data:
            old_dict = {}
            for line in old_data.split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1)
                    old_dict[k.strip()] = v.strip().replace("'", "")
            new_dict = {}
            for line in new_data.split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1)
                    new_dict[k.strip()] = v.strip().replace("'", "")
            
            for key, new_val in new_dict.items():
                old_val = old_dict.get(key)
                if old_val and old_val != new_val:
                    html += f"<tr><td class='p-1 fw-semibold text-muted' style='width: 100px;'>{key}:</td><td class='p-1'><span class='text-muted text-decoration-line-through me-2'>{old_val}</span> <i class='fas fa-arrow-right text-muted mx-2' style='font-size: 0.7rem;'></i> <span class='text-success fw-medium'>{new_val}</span></td></tr>"
                elif not old_val:
                    html += f"<tr><td class='p-1 fw-semibold text-muted' style='width: 100px;'>{key}:</td><td class='p-1'><span class='text-success fw-medium'>{new_val}</span></td></tr>"

        # Case 3: Addition
        elif action == 'ADD' and new_data:
            lines = new_data.split('\n')
            for line in lines:
                if ':' in line:
                    key, val = line.split(':', 1)
                    val = val.strip().replace("'", "")
                    html += f"<tr><td class='p-1 fw-semibold text-muted' style='width: 100px;'>{key.strip()}:</td><td class='p-1 text-success fw-medium'>{val}</td></tr>"

        # Fallback
        if "<tr>" not in html:
            if new_data and new_data != 'None' and 'Profile updated via UI' not in new_data:
                html += f"<tr><td class='p-0 text-muted'>{new_data}</td></tr>"
            elif old_data and old_data != 'None':
                html += f"<tr><td class='p-0 text-muted'>{old_data}</td></tr>"
            else:
                html += "<tr><td class='p-0 text-muted fst-italic'>No additional details</td></tr>"

    html += "</tbody></table></div>"
    return mark_safe(html)

@register.filter
def get_initials(name):
    if not name: return ""
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    elif len(parts) == 1:
        return parts[0][:2].upper()
    return "U"
