import logging

logger = logging.getLogger(__name__)

SAFE_READ_COMMANDS = {"monitor-traffic", "print", "ping"}


def log_blocked_write(action_desc: str):
    """Logs blocked write attempts both to Python logger and DB SystemLog."""
    logger.warning(f"[ROUTER_MODE=read_only] {action_desc}")
    try:
        from billing.models import SystemLog

        SystemLog.objects.create(
            table_name="MikrotikRouter",
            record_id="0",
            action="BLOCKED_WRITE",
            changed_by="RouterSafetyGuard",
            target_name="ROUTER_MODE=read_only",
            old_data="",
            new_data=action_desc,
        )
    except Exception:
        pass


class ReadOnlyResourceWrapper:
    """Wraps a RouterOS API resource, allowing reads (.get()) and blocking writes (.add(), .set(), .remove())."""

    def __init__(self, real_resource, device_name: str, path: str):
        self._real_resource = real_resource
        self.device_name = device_name
        self.path = path

    def get(self, *args, **kwargs):
        return self._real_resource.get(*args, **kwargs)

    def add(self, *args, **kwargs):
        desc = f"Blocked add() on {self.path} for device '{self.device_name}' with args={kwargs}"
        log_blocked_write(desc)
        return "*read_only_blocked*"

    def set(self, *args, **kwargs):
        desc = f"Blocked set() on {self.path} for device '{self.device_name}' with args={kwargs}"
        log_blocked_write(desc)
        return None

    def remove(self, *args, **kwargs):
        desc = f"Blocked remove() on {self.path} for device '{self.device_name}' with args={kwargs}"
        log_blocked_write(desc)
        return None

    def call(self, command, *args, **kwargs):
        if command in SAFE_READ_COMMANDS:
            return self._real_resource.call(command, *args, **kwargs)
        desc = f"Blocked call('{command}') on {self.path} for device '{self.device_name}' with args={kwargs}"
        log_blocked_write(desc)
        return []

    def __getattr__(self, item):
        return getattr(self._real_resource, item)


class ReadOnlyApiWrapper:
    """Wraps a RouterOS API pool/client, returning ReadOnlyResourceWrapper for all resources."""

    def __init__(self, real_api, device_name: str):
        self._real_api = real_api
        self.device_name = device_name

    def get_resource(self, path: str):
        real_res = self._real_api.get_resource(path)
        return ReadOnlyResourceWrapper(real_res, self.device_name, path)

    def get_binary_resource(self, path: str):
        real_res = self._real_api.get_binary_resource(path)
        return ReadOnlyResourceWrapper(real_res, self.device_name, path)

    def __getattr__(self, item):
        return getattr(self._real_api, item)
