import json
from .models import SystemLog

def log_system_action(table_name, record_id, action, changed_by, target_name=None, old_data=None, new_data=None):
    """
    Helper function to record an audit log in the SystemLog model.
    old_data and new_data should be dicts, which will be stored as JSON text.
    """
    old_json = json.dumps(old_data) if old_data else None
    new_json = json.dumps(new_data) if new_data else None

    SystemLog.objects.create(
        table_name=table_name,
        record_id=str(record_id),
        action=action,
        changed_by=changed_by,
        target_name=target_name,
        old_data=old_json,
        new_data=new_json
    )
