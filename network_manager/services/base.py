import logging
import socket
import routeros_api
from network_manager.models import MikrotikDevice

logger = logging.getLogger(__name__)

class MikrotikBase:
        def __init__(self, device: MikrotikDevice):
            self.device = device

            # Convert port to integer, fallback to standard API port 8728 if missing
            try:
                port = int(device.api_port)
            except (ValueError, TypeError):
                port = 8728

            # Handle empty/None passwords for test routers
            password = device.api_password if device.api_password else ""

            # Set a default timeout for this thread's sockets to prevent infinite hangs
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(5.0)
            try:
                # We set up the API connection pool
                self.connection = routeros_api.RouterOsApiPool(
                    host=device.ip_address,
                    username=device.api_username,
                    password=password,
                    port=port,
                    plaintext_login=True,  # Modern RouterOS versions use plain login sequence for API
                    use_ssl=False  # Set to True if using secure port (e.g., 8729)
                )
            finally:
                socket.setdefaulttimeout(old_timeout)
            self._connection_failed = False

        def _get_api(self):
            """Handles connection securely with timeouts and returns the API instance, with automatic fallback for older RouterOS versions."""
            if getattr(self, '_connection_failed', False):
                raise ConnectionError(f"Previous connection attempt to {self.device.ip_address} failed, skipping retry.")

            try:
                # First attempt with plaintext_login (RouterOS v6.43+)
                old_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(5.0)
                try:
                    return self.connection.get_api()
                finally:
                    socket.setdefaulttimeout(old_timeout)
            except routeros_api.exceptions.RouterOsApiCommunicationError as e:
                # If the error string contains "invalid user name or password (6)" and we were using plaintext login,
                # it might actually be an older RouterOS version expecting a challenge-response (plaintext_login=False).
                logger.warning(f"Plaintext login failed for {self.device.device_name}, retrying with legacy authentication...")
                
                try:
                    old_timeout = socket.getdefaulttimeout()
                    socket.setdefaulttimeout(5.0)
                    try:
                        # Re-create connection with legacy auth
                        self.connection = routeros_api.RouterOsApiPool(
                            host=self.device.ip_address,
                            username=self.device.api_username,
                            password=self.device.api_password if self.device.api_password else "",
                            port=self.connection.port,
                            plaintext_login=False,
                            use_ssl=self.connection.use_ssl
                        )
                        return self.connection.get_api()
                    finally:
                        socket.setdefaulttimeout(old_timeout)
                except Exception as retry_e:
                    self._connection_failed = True
                    logger.error(f"Legacy Auth Failed for {self.device.device_name}: {retry_e}")
                    raise ConnectionError(f"Could not authenticate to {self.device.device_name} API. Check credentials.") from retry_e
                    
            except Exception as e:
                self._connection_failed = True
                logger.error(f"Timeout/Error connecting to Mikrotik API on {self.device.ip_address}: {e}")
                raise ConnectionError(f"Could not connect to {self.device.device_name} API. Check IP/Port and credentials.") from e

