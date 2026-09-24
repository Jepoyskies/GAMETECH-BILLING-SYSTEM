import logging

logger = logging.getLogger(__name__)


class DryRunResource:
    """
    Simulates a RouterOS API endpoint/resource (e.g. /ppp/secret, /ppp/active, /system/resource).
    Captures read/write/delete operations in-memory without sending network traffic.
    """

    def __init__(self, path: str, device_name: str = "DryRunRouter"):
        self.path = path
        self.device_name = device_name
        self._store = []
        self._init_defaults()

    def _init_defaults(self):
        if self.path == "/system/resource":
            self._store = [
                {
                    "uptime": "14d 06:12:33",
                    "version": "7.12 (stable)",
                    "cpu-load": "8",
                    "free-memory": "268435456",
                    "total-memory": "536870912",
                    "board-name": "CCR2004-1G-12S+2XS (DRY_RUN)",
                    "architecture-name": "arm64",
                }
            ]
        elif self.path == "/ppp/profile":
            self._store = [
                {
                    "id": "*P1",
                    "name": "default",
                    "local-address": "10.10.10.1",
                    "remote-address": "pool_default",
                    "rate-limit": "15M/15M",
                },
                {
                    "id": "*P2",
                    "name": "GTipid Fiber 1000",
                    "local-address": "10.10.10.1",
                    "remote-address": "pool1",
                    "rate-limit": "35M/35M",
                },
                {
                    "id": "*P3",
                    "name": "GFiber 1500",
                    "local-address": "10.10.10.1",
                    "remote-address": "pool1",
                    "rate-limit": "60M/60M",
                },
            ]
        elif self.path == "/ppp/secret":
            self._store = [
                {
                    "id": "*S1",
                    "name": "sample_pppoe_user",
                    "password": "sample_password",
                    "profile": "GTipid Fiber 1000",
                    "comment": "Active PPPoE Secret (Dry Run)",
                    "service": "pppoe",
                    "disabled": "false",
                }
            ]
        elif self.path == "/ppp/active":
            self._store = [
                {
                    "id": "*A1",
                    "name": "sample_pppoe_user",
                    "service": "pppoe",
                    "caller-id": "00:11:22:33:44:55",
                    "address": "10.10.10.50",
                    "uptime": "2h15m",
                    "bytes-in": "104857600",
                    "bytes-out": "524288000",
                }
            ]
        elif self.path == "/interface/ethernet":
            self._store = [
                {"name": "ether1", "status": "link-ok"},
                {"name": "sfp-sfpplus1", "status": "link-ok"},
            ]
        elif self.path == "/interface":
            self._store = [
                {
                    "id": "*I1",
                    "name": "ether1",
                    "type": "ether",
                    "running": "true",
                    "disabled": "false",
                },
                {
                    "id": "*I2",
                    "name": "sfp-sfpplus1",
                    "type": "ether",
                    "running": "true",
                    "disabled": "false",
                },
            ]
        elif self.path == "/queue/simple":
            self._store = []

    def get(self, **kwargs):
        logger.info(
            f"[ROUTER_DRY_RUN] {self.device_name} {self.path}.get({kwargs})"
        )
        results = self._store
        for key, val in kwargs.items():
            results = [
                item for item in results if str(item.get(key)) == str(val)
            ]
        return list(results)

    def add(self, **kwargs):
        new_id = f"*{len(self._store) + 100}"
        item = dict(kwargs)
        item["id"] = new_id
        self._store.append(item)
        logger.info(
            f"[ROUTER_DRY_RUN] {self.device_name} {self.path}.add({kwargs}) -> id={new_id}"
        )
        return new_id

    def set(self, id=None, **kwargs):
        logger.info(
            f"[ROUTER_DRY_RUN] {self.device_name} {self.path}.set(id={id}, {kwargs})"
        )
        target_name = kwargs.get("name")
        found = False
        for item in self._store:
            if (id and item.get("id") == str(id)) or (
                target_name and item.get("name") == str(target_name)
            ):
                item.update(kwargs)
                found = True
                break
        if not found and id:
            kwargs["id"] = str(id)
            self._store.append(kwargs)

    def remove(self, id=None, **kwargs):
        logger.info(
            f"[ROUTER_DRY_RUN] {self.device_name} {self.path}.remove(id={id}, {kwargs})"
        )
        if id:
            self._store = [
                item for item in self._store if item.get("id") != str(id)
            ]

    def call(self, command, kwargs=None):
        logger.info(
            f"[ROUTER_DRY_RUN] {self.device_name} {self.path}.call({command}, {kwargs})"
        )
        if self.path == "/interface/ethernet" and command == "monitor":
            return [
                {
                    "sfp-rx-power": "-19.5",
                    "sfp-tx-power": "2.1",
                    "sfp-temperature": "35.4",
                }
            ]
        return []


class DryRunRouterApi:
    """
    Simulates the RouterOsApi instance returned by connection.get_api().
    """

    def __init__(self, device_name: str = "DryRunRouter"):
        self.device_name = device_name
        self._resources = {}

    def get_resource(self, path: str):
        if path not in self._resources:
            self._resources[path] = DryRunResource(path, self.device_name)
        return self._resources[path]

    def get_binary_resource(self, path: str):
        return self.get_resource(path)


class DryRunConnectionPool:
    """
    Simulates RouterOsApiPool.
    """

    def __init__(self, device_name: str = "DryRunRouter"):
        self.device_name = device_name
        self.api = DryRunRouterApi(device_name)

    def get_api(self):
        logger.info(
            f"[ROUTER_DRY_RUN] Intercepted RouterOS connection to {self.device_name} (STUBBED)"
        )
        return self.api

    def disconnect(self):
        pass
