from django import template
from django.utils.safestring import mark_safe

register = template.Library()


from django.core.cache import cache


def _get_lookup_map(cache_key, model_path, id_field="id", name_field="name"):
    mapping = cache.get(cache_key)
    if mapping is None:
        try:
            from django.apps import apps

            app_label, model_name = model_path.split(".")
            model_cls = apps.get_model(app_label, model_name)
            mapping = dict(model_cls.objects.values_list(id_field, name_field))
            cache.set(cache_key, mapping, 60)
        except Exception:
            mapping = {}
    return mapping


def resolve_field_and_value(key, val):
    clean_val = str(val).strip().replace("'", "").replace('"', "")
    k_norm = key.strip()
    k_lower = k_norm.lower().replace("_", " ")

    if "plan" in k_lower:
        label = "Plan"
        if clean_val.isdigit():
            plans = _get_lookup_map(
                "cache_log_plans_map", "billing.SubscriptionPlan", "id", "name"
            )
            return label, plans.get(int(clean_val), clean_val)
        return label, clean_val

    if "account type" in k_lower:
        label = "Account Type"
        if clean_val.isdigit():
            types = _get_lookup_map(
                "cache_log_actypes_map", "billing.AccountType", "id", "type_name"
            )
            return label, types.get(int(clean_val), clean_val)
        return label, clean_val

    if "router" in k_lower or "device" in k_lower or "mikrotik" in k_lower:
        label = "Router"
        if clean_val.isdigit():
            devices = _get_lookup_map(
                "cache_log_devices_map",
                "network_manager.MikrotikDevice",
                "id",
                "device_name",
            )
            return label, devices.get(int(clean_val), clean_val)
        return label, clean_val

    if "barangay" in k_lower:
        label = "Barangay"
        if clean_val.isdigit():
            barangays = _get_lookup_map(
                "cache_log_barangays_map", "billing.Barangay", "id", "name"
            )
            return label, barangays.get(int(clean_val), clean_val)
        return label, clean_val

    if "agent" in k_lower:
        label = "Agent"
        if clean_val.isdigit():
            agents = _get_lookup_map(
                "cache_log_agents_map", "billing.Agent", "id", "name"
            )
            return label, agents.get(int(clean_val), clean_val)
        return label, clean_val

    if k_norm.endswith(" ID"):
        k_norm = k_norm[:-3].strip()
    elif k_norm.endswith("_id"):
        k_norm = k_norm[:-3].replace("_", " ").title().strip()

    return k_norm, clean_val


@register.filter
def format_log_details(log):
    sentences = []
    old_data = str(log.old_data).strip() if log.old_data else ""
    new_data = str(log.new_data).strip() if log.new_data else ""
    action = str(log.action).upper()

    if old_data == "null":
        old_data = ""
    if new_data == "null":
        new_data = ""

    bg_class = (
        "bg-danger-subtle text-danger" if action == "DELETE" else "bg-light text-dark"
    )
    border_class = "border-danger-subtle" if action == "DELETE" else "border-light"

    html = f"<div class='p-3 rounded-3 {bg_class} {border_class} border' style='font-size: 0.85rem; font-family: Inter, sans-serif;'>"
    html += "<table class='table table-sm table-borderless mb-0' style='background: transparent;'>"
    html += "<tbody>"

    # Action: DELETE
    if action == "DELETE" and old_data:
        parts = {}
        for line in old_data.split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                parts[k.strip()] = v.strip().replace("'", "")

        if "Amount" in parts:
            amt = parts.get("Amount", "")
            method = parts.get("Method", "")
            ref = parts.get("Reference", "")
            html += f"<tr><td class='text-danger p-0 fw-medium'><i class='fas fa-exclamation-triangle me-2'></i> Deleted {method} Payment of ₱{amt} (Ref: {ref})</td></tr>"
        else:
            for k, v in parts.items():
                resolved_key, res_v = resolve_field_and_value(k, v)
                html += f"<tr><td class='p-0 text-danger fw-semibold' style='width: 120px;'>{resolved_key}:</td><td class='p-0 text-danger'>{res_v}</td></tr>"

    # Action: ADD / UPDATE
    else:
        # Case 1: Profile update with -> or → (arrow format)
        if "→" in old_data or "->" in old_data:
            lines = old_data.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if "→" in line or "->" in line:
                    sep = "→" if "→" in line else "->"
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        raw_key = parts[0].strip()
                        raw_old, raw_new = parts[1].split(sep, 1)
                        key, old_val = resolve_field_and_value(raw_key, raw_old)
                        _, new_val = resolve_field_and_value(raw_key, raw_new)
                        html += f"<tr><td class='p-1 fw-semibold text-muted' style='width: 100px;'>{key}:</td><td class='p-1'><span class='text-muted text-decoration-line-through me-2'>{old_val}</span> <i class='fas fa-arrow-right text-muted mx-2' style='font-size: 0.7rem;'></i> <span class='text-success fw-medium'>{new_val}</span></td></tr>"

        # Case 2: Key-value Updates (no arrows)
        elif "UPDATE" in action and old_data and new_data:
            old_dict = {}
            for line in old_data.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    old_dict[k.strip()] = v.strip().replace("'", "")
            new_dict = {}
            for line in new_data.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    new_dict[k.strip()] = v.strip().replace("'", "")

            for key, new_val in new_dict.items():
                old_val = old_dict.get(key)
                if old_val and old_val != new_val:
                    resolved_key, res_old = resolve_field_and_value(key, old_val)
                    _, res_new = resolve_field_and_value(key, new_val)
                    html += f"<tr><td class='p-1 fw-semibold text-muted' style='width: 100px;'>{resolved_key}:</td><td class='p-1'><span class='text-muted text-decoration-line-through me-2'>{res_old}</span> <i class='fas fa-arrow-right text-muted mx-2' style='font-size: 0.7rem;'></i> <span class='text-success fw-medium'>{res_new}</span></td></tr>"
                elif not old_val:
                    resolved_key, res_new = resolve_field_and_value(key, new_val)
                    html += f"<tr><td class='p-1 fw-semibold text-muted' style='width: 100px;'>{resolved_key}:</td><td class='p-1'><span class='text-success fw-medium'>{res_new}</span></td></tr>"

        # Case 3: Addition
        elif action == "ADD" and new_data:
            lines = new_data.split("\n")
            for line in lines:
                if ":" in line:
                    key, val = line.split(":", 1)
                    resolved_key, res_val = resolve_field_and_value(key, val)
                    html += f"<tr><td class='p-1 fw-semibold text-muted' style='width: 100px;'>{resolved_key}:</td><td class='p-1 text-success fw-medium'>{res_val}</td></tr>"

        # Fallback
        if "<tr>" not in html:
            if (
                new_data
                and new_data != "None"
                and "Profile updated via UI" not in new_data
            ):
                html += f"<tr><td class='p-0 text-muted'>{new_data}</td></tr>"
            elif old_data and old_data != "None":
                html += f"<tr><td class='p-0 text-muted'>{old_data}</td></tr>"
            else:
                html += "<tr><td class='p-0 text-muted fst-italic'>No additional details</td></tr>"

    html += "</tbody></table></div>"
    return mark_safe(html)


@register.filter
def get_initials(name):
    if not name:
        return ""
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    elif len(parts) == 1:
        return parts[0][:2].upper()
    return "U"


@register.filter
def specific_action(log):
    if hasattr(log, "specific_action"):
        return log.specific_action
    return str(getattr(log, "action", log))


@register.filter
def action_pill_class(action_text):
    text = str(action_text).upper()
    if any(k in text for k in ["DELETE", "REMOVE", "SUSPEND", "RESET", "VOID", "UNVERIFY", "FAIL"]):
        return "pill-expired"
    elif any(k in text for k in ["ADD", "CREATE", "LOGIN", "NEW", "PAYMENT", "REACTIVATE", "VERIFY"]):
        return "pill-active"
    else:
        return "pill-pending"

