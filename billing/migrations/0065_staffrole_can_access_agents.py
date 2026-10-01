from django.db import migrations, models


def promote_agents_to_own_module(apps, schema_editor):
    """
    Agents is now a top-level sidebar module of its own, no longer a
    Dispatch subtab. Carry every existing grant across so nobody loses
    access on upgrade: dispatch.agents -> agents.agents, and the
    dispatch action block -> the agents action block.
    """
    StaffRole = apps.get_model("billing", "StaffRole")
    for r in StaffRole.objects.all():
        sp = r.subtab_permissions if isinstance(r.subtab_permissions, dict) else {}
        dispatch = sp.get("dispatch") if isinstance(sp.get("dispatch"), dict) else {}
        allowed = bool(dispatch.get("agents", r.can_access_dispatch))

        dispatch.pop("agents", None)
        sp["dispatch"] = dispatch
        sp["agents"] = {"agents": allowed}

        actions = sp.get("_actions")
        if isinstance(actions, dict) and isinstance(actions.get("dispatch"), dict):
            actions["agents"] = actions["dispatch"]

        r.can_access_agents = allowed
        r.subtab_permissions = sp
        r.save(update_fields=["can_access_agents", "subtab_permissions"])


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0064_drop_plaintext_password_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffrole",
            name="can_access_agents",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(promote_agents_to_own_module, migrations.RunPython.noop),
    ]