import json
import logging
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.db.models import Max
from .models import Team, Technician, ConfigOption, AuditLog

logger = logging.getLogger(__name__)

LOCKED_SYSTEM_LABELS = {'done', 'cancelled', 'pending', 'installation', 'repair', 'concern', 'inquiry'}


def log_audit(action, entity_type, entity_id, actor, summary=None, before=None, after=None):
    try:
        AuditLog.objects.create(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor if (actor and actor.is_authenticated) else None,
            summary=summary,
            before_data=before,
            after_data=after
        )
    except Exception as e:
        logger.warning(f"Failed to record dispatch audit log: {e}")


@login_required
def management_view(request):
    User = get_user_model()

    teams = Team.objects.prefetch_related('members').all()
    technicians = Technician.objects.select_related('team', 'user').all()
    accounts = User.objects.filter(is_active=True).order_by('-date_joined')

    # Aggregate target statistics
    total_daily_target = sum(t.target_per_day or 5 for t in technicians)
    total_monthly_target = sum(t.target_per_month or 100 for t in technicians)

    # Auto-seed baseline options if table is empty
    if not ConfigOption.objects.filter(module='DISPATCH').exists():
        defaults = [
            ('DISPATCH', 'STATUS', 'Pending', '#f59e0b', 1, True),
            ('DISPATCH', 'STATUS', 'Assigned', '#3b82f6', 2, False),
            ('DISPATCH', 'STATUS', 'In Progress', '#06b6d4', 3, False),
            ('DISPATCH', 'STATUS', 'Done', '#10b981', 4, True),
            ('DISPATCH', 'STATUS', 'Cancelled', '#ef4444', 5, True),
            ('DISPATCH', 'TYPE', 'Installation', '#10b981', 1, True),
            ('DISPATCH', 'TYPE', 'Repair', '#ef4444', 2, True),
            ('DISPATCH', 'TYPE', 'Cignal', '#a855f7', 3, False),
            ('DISPATCH', 'TYPE', 'Migration', '#06b6d4', 4, False),
            ('MONITORING', 'CHAT_TYPE', 'Inquiry', '#3b82f6', 1, True),
            ('MONITORING', 'CHAT_TYPE', 'Concern', '#f59e0b', 2, True),
            ('MONITORING', 'CHAT_TYPE', 'Follow-up', '#6366f1', 3, False),
        ]
        for mod, ltype, lbl, clr, sorder, hcode in defaults:
            ConfigOption.objects.get_or_create(
                module=mod, list_type=ltype, label=lbl,
                defaults={'color': clr, 'sort_order': sorder, 'active': True, 'hardcoded': hcode}
            )

    config_options = ConfigOption.objects.all().order_by('module', 'list_type', 'sort_order')
    for opt in config_options:
        opt.is_locked = opt.hardcoded or (opt.label.strip().lower() in LOCKED_SYSTEM_LABELS)

    return render(request, 'dispatch/management.html', {
        'teams': teams,
        'technicians': technicians,
        'accounts': accounts,
        'total_daily_target': total_daily_target,
        'total_monthly_target': total_monthly_target,
        'config_options': config_options,
    })


# ---------------------------------------------------------------------------
# Team CRUD APIs
# ---------------------------------------------------------------------------

@login_required
@require_POST
def api_team_create(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'success': False, 'error': 'Team name is required.'}, status=400)
    if Team.objects.filter(name__iexact=name).exists():
        return JsonResponse({'success': False, 'error': f'Team "{name}" already exists.'}, status=400)
    team = Team.objects.create(name=name)
    log_audit('CREATE', 'Team', team.id, request.user, summary=f"Created field team: {name}", after={'name': name})
    return JsonResponse({'success': True, 'team': {'id': team.id, 'name': team.name, 'members_count': 0}})


@login_required
@require_POST
def api_team_update(request, team_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    team = get_object_or_404(Team, id=team_id)
    data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'success': False, 'error': 'Team name is required.'}, status=400)
    if Team.objects.filter(name__iexact=name).exclude(id=team.id).exists():
        return JsonResponse({'success': False, 'error': f'Team "{name}" already exists.'}, status=400)
    before = {'name': team.name}
    team.name = name
    team.save()
    log_audit('UPDATE', 'Team', team.id, request.user, summary=f"Updated team #{team.id} to {name}", before=before, after={'name': name})
    return JsonResponse({'success': True, 'team': {'id': team.id, 'name': team.name}})


@login_required
@require_POST
def api_team_delete(request, team_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    team = get_object_or_404(Team, id=team_id)
    name = team.name
    team.delete()
    log_audit('DELETE', 'Team', team_id, request.user, summary=f"Deleted field team: {name}")
    return JsonResponse({'success': True, 'message': f'Team "{name}" deleted successfully.'})


# ---------------------------------------------------------------------------
# Technician CRUD & Target APIs
# ---------------------------------------------------------------------------

@login_required
@require_POST
def api_technician_create(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    User = get_user_model()
    data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
    name = data.get('name', '').strip()
    contact_number = data.get('contact_number', '').strip()
    team_id = data.get('team_id')
    user_id = data.get('user_id')

    try:
        target_per_day = int(data.get('target_per_day', 5))
    except (ValueError, TypeError):
        target_per_day = 5
    try:
        target_per_month = int(data.get('target_per_month', 100))
    except (ValueError, TypeError):
        target_per_month = 100

    if not name:
        return JsonResponse({'success': False, 'error': 'Technician name is required.'}, status=400)
    if Technician.objects.filter(name__iexact=name).exists():
        return JsonResponse({'success': False, 'error': f'Technician "{name}" already exists.'}, status=400)

    team = Team.objects.filter(id=team_id).first() if team_id else None
    user = User.objects.filter(id=user_id).first() if user_id else None

    tech = Technician.objects.create(
        name=name,
        contact_number=contact_number,
        team=team,
        user=user,
        target_per_day=target_per_day,
        target_per_month=target_per_month,
        is_available=True
    )
    log_audit('CREATE', 'Technician', tech.id, request.user, summary=f"Created technician: {name}", after={'name': name, 'team': team.name if team else None})
    return JsonResponse({'success': True, 'technician': {'id': tech.id, 'name': tech.name}})


@login_required
@require_POST
def api_technician_update(request, tech_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    tech = get_object_or_404(Technician, id=tech_id)
    User = get_user_model()
    data = json.loads(request.body.decode('utf-8')) if request.body else request.POST

    name = data.get('name', '').strip()
    if name:
        if Technician.objects.filter(name__iexact=name).exclude(id=tech.id).exists():
            return JsonResponse({'success': False, 'error': f'Technician "{name}" already exists.'}, status=400)
        tech.name = name

    if 'contact_number' in data:
        tech.contact_number = str(data.get('contact_number', '')).strip()

    if 'team_id' in data:
        team_id = data.get('team_id')
        tech.team = Team.objects.filter(id=team_id).first() if team_id else None

    if 'user_id' in data:
        user_id = data.get('user_id')
        tech.user = User.objects.filter(id=user_id).first() if user_id else None

    if 'target_per_day' in data:
        try:
            tech.target_per_day = int(data.get('target_per_day', 5))
        except (ValueError, TypeError):
            pass

    if 'target_per_month' in data:
        try:
            tech.target_per_month = int(data.get('target_per_month', 100))
        except (ValueError, TypeError):
            pass

    tech.save()
    log_audit('UPDATE', 'Technician', tech.id, request.user, summary=f"Updated technician #{tech.id} ({tech.name})")
    return JsonResponse({
        'success': True,
        'technician': {
            'id': tech.id,
            'name': tech.name,
            'contact_number': tech.contact_number,
            'team_id': tech.team_id,
            'team_name': tech.team.name if tech.team else 'Unassigned',
            'target_per_day': tech.target_per_day,
            'target_per_month': tech.target_per_month,
        }
    })


@login_required
@require_POST
def api_technician_delete(request, tech_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    tech = get_object_or_404(Technician, id=tech_id)
    name = tech.name
    tech.delete()
    log_audit('DELETE', 'Technician', tech_id, request.user, summary=f"Deleted technician: {name}")
    return JsonResponse({'success': True, 'message': f'Technician "{name}" deleted successfully.'})


@login_required
@require_POST
def api_technician_targets_update(request, tech_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    tech = get_object_or_404(Technician, id=tech_id)
    data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
    try:
        daily = int(data.get('target_per_day', tech.target_per_day or 5))
        monthly = int(data.get('target_per_month', tech.target_per_month or 100))
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid target numbers.'}, status=400)

    tech.target_per_day = daily
    tech.target_per_month = monthly
    tech.save(update_fields=['target_per_day', 'target_per_month', 'updated_at'])
    log_audit('UPDATE', 'Technician', tech.id, request.user, summary=f"Updated targets for {tech.name}: {daily}/day, {monthly}/mo")
    return JsonResponse({
        'success': True,
        'target_per_day': daily,
        'target_per_month': monthly,
        'tech_id': tech.id
    })


# ---------------------------------------------------------------------------
# Dropdown Options Config APIs
# ---------------------------------------------------------------------------

@login_required
@require_POST
def api_config_options_create(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
    label = data.get('label', '').strip()
    module = data.get('module', 'MONITORING').strip().upper()
    list_type = data.get('list_type', 'STATUS').strip().upper()
    color = data.get('color', '#6b7280').strip()
    active = data.get('active', True)
    if isinstance(active, str):
        active = active.lower() in ('true', '1', 'yes')

    if not label:
        return JsonResponse({'success': False, 'error': 'Label is required.'}, status=400)
    if module not in ['DISPATCH', 'MONITORING']:
        return JsonResponse({'success': False, 'error': 'Invalid module.'}, status=400)
    if list_type not in ['STATUS', 'TYPE', 'CHAT_TYPE']:
        return JsonResponse({'success': False, 'error': 'Invalid list type.'}, status=400)

    if ConfigOption.objects.filter(module=module, list_type=list_type, label__iexact=label).exists():
        return JsonResponse({'success': False, 'error': f'An option with label "{label}" already exists in {module} {list_type}.'}, status=400)

    max_order = ConfigOption.objects.filter(module=module, list_type=list_type).aggregate(Max('sort_order'))['sort_order__max'] or 0
    opt = ConfigOption.objects.create(
        module=module,
        list_type=list_type,
        label=label,
        color=color,
        sort_order=max_order + 1,
        active=active,
        hardcoded=False
    )
    log_audit('CREATE', 'ConfigOption', opt.id, request.user, summary=f"Created {module} {list_type} option: {label}", after={'label': label, 'color': color, 'active': active})
    return JsonResponse({
        'success': True,
        'option': {
            'id': opt.id, 'module': opt.module, 'list_type': opt.list_type,
            'label': opt.label, 'color': opt.color, 'active': opt.active, 'hardcoded': opt.hardcoded
        }
    })


@login_required
@require_POST
def api_config_options_update(request, option_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    opt = get_object_or_404(ConfigOption, id=option_id)
    data = json.loads(request.body.decode('utf-8')) if request.body else request.POST

    is_locked = opt.hardcoded or (opt.label.strip().lower() in LOCKED_SYSTEM_LABELS)
    before_data = {'label': opt.label, 'color': opt.color, 'active': opt.active}

    new_label = data.get('label', '').strip()
    if new_label and not is_locked:
        if ConfigOption.objects.filter(module=opt.module, list_type=opt.list_type, label__iexact=new_label).exclude(id=opt.id).exists():
            return JsonResponse({'success': False, 'error': f'An option with label "{new_label}" already exists.'}, status=400)
        opt.label = new_label

    if 'color' in data:
        opt.color = str(data['color']).strip()

    if 'active' in data:
        val = data['active']
        if isinstance(val, str):
            opt.active = val.lower() in ('true', '1', 'yes')
        else:
            opt.active = bool(val)

    opt.save()
    after_data = {'label': opt.label, 'color': opt.color, 'active': opt.active}
    log_audit('UPDATE', 'ConfigOption', opt.id, request.user, summary=f"Updated config option #{opt.id} ({opt.label})", before=before_data, after=after_data)

    return JsonResponse({
        'success': True,
        'option': {
            'id': opt.id, 'module': opt.module, 'list_type': opt.list_type,
            'label': opt.label, 'color': opt.color, 'active': opt.active, 'hardcoded': is_locked
        }
    })


@login_required
@require_POST
def api_config_options_delete(request, option_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    opt = get_object_or_404(ConfigOption, id=option_id)
    if opt.hardcoded or (opt.label.strip().lower() in LOCKED_SYSTEM_LABELS):
        return JsonResponse({'success': False, 'error': f'"{opt.label}" is a system-critical option and cannot be deleted. You can recolor it or toggle active.'}, status=400)

    label = opt.label
    opt.delete()
    log_audit('DELETE', 'ConfigOption', option_id, request.user, summary=f"Deleted custom config option: {label}")
    return JsonResponse({'success': True, 'message': f'Option "{label}" deleted successfully.'})
