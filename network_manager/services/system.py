import logging
import socket
import routeros_api
from .models import MikrotikDevice

logger = logging.getLogger(__name__)

class MikrotikSystemMixin:
        def get_system_resources(self):
            """
            Retrieves CPU, RAM, and version info.
            """
            try:
                api = self._get_api()
                resources = api.get_resource('/system/resource').get()
                self.connection.disconnect()
                return resources[0] if resources else {}
            except Exception as e:
                logger.error(f"Failed to get system resources from {self.device.device_name}: {e}")
                return {}

        def get_optical_readings(self):
            """
            Retrieves SFP optical power readings.
            """
            try:
                api = self._get_api()
                eth_api = api.get_resource('/interface/ethernet')
                interfaces = eth_api.get()
                sfp_interfaces = [i['name'] for i in interfaces if 'sfp' in i.get('name', '').lower()]
                
                readings = []
                for name in sfp_interfaces:
                    try:
                        monitor = eth_api.call('monitor', {'numbers': name, 'once': ''})
                        if monitor:
                            monitor[0]['name'] = name
                            readings.append(monitor[0])
                    except Exception:
                        pass
                self.connection.disconnect()
                return readings
            except Exception as e:
                logger.error(f"Failed to get optical readings from {self.device.device_name}: {e}")
                return []

        def get_simple_queues(self):
            """
            Retrieves simple queues from the Mikrotik device.
            Useful for monitoring live bandwidth usage of PPPoE users.
            """
            try:
                api = self._get_api()

                # Access the /queue/simple endpoint with stats
                queues_api = api.get_resource('/queue/simple')

                # 'stats' attribute might not be retrieved by default without specifying it,
                # but usually routeros_api gets all attributes.
                queues = queues_api.get()

                self.connection.disconnect()
                return queues
            except Exception as e:
                logger.error(
                    f"Failed to get simple queues from {self.device.device_name}: {e}")
                return []

        def get_interfaces_traffic(self, interface_names):
            """
            Retrieves live traffic from specified interfaces individually to prevent batch failures.
            interface_names: list of interface names
            """
            if not interface_names:
                return []
            traffic_results = []
            try:
                api = self._get_api()
                interfaces_api = api.get_resource('/interface')
                for name in interface_names:
                    try:
                        traffic = interfaces_api.call('monitor-traffic', {
                            'interface': name,
                            'once': ''
                        })
                        if traffic:
                            traffic_results.extend(traffic)
                    except Exception:
                        # Ignore single interface errors (e.g. disconnected)
                        pass
                self.connection.disconnect()
                return traffic_results
            except Exception as e:
                logger.error(f"Failed to get interface traffic from {self.device.device_name}: {e}")
                return []

