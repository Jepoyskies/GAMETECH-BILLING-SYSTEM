import logging
import routeros_api
from .models import MikrotikDevice

logger = logging.getLogger(__name__)


class MikrotikAPI:
    """
    Utility class to interact with Mikrotik devices using the RouterOS API.
    We highly recommend 'RouterOS-api' over Netmiko for managing secrets and active users
    because it returns clean structured data (dictionaries) instead of raw CLI text that
    requires fragile regex parsing.
    """

    def __init__(self, device: MikrotikDevice):
        self.device = device

        # Convert port to integer, fallback to standard API port 8728 if missing
        try:
            port = int(device.api_port)
        except (ValueError, TypeError):
            port = 8728

        # Handle empty/None passwords for test routers
        password = device.api_password if device.api_password else ""

        # We set up the API connection pool
        self.connection = routeros_api.RouterOsApiPool(
            host=device.ip_address,
            username=device.api_username,
            password=password,
            port=port,
            plaintext_login=True,  # Modern RouterOS versions use plain login sequence for API
            use_ssl=False  # Set to True if using secure port (e.g., 8729)
        )

    def _get_api(self):
        """Handles connection securely with timeouts and returns the API instance, with automatic fallback for older RouterOS versions."""
        try:
            # First attempt with plaintext_login (RouterOS v6.43+)
            return self.connection.get_api()
        except routeros_api.exceptions.RouterOsApiCommunicationError as e:
            # If the error string contains "invalid user name or password (6)" and we were using plaintext login,
            # it might actually be an older RouterOS version expecting a challenge-response (plaintext_login=False).
            logger.warning(f"Plaintext login failed for {self.device.device_name}, retrying with legacy authentication...")
            
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
            except Exception as retry_e:
                logger.error(f"Legacy Auth Failed for {self.device.device_name}: {retry_e}")
                raise ConnectionError(f"Could not authenticate to {self.device.device_name} API. Check credentials.") from retry_e
                
        except Exception as e:
            logger.error(f"Timeout/Error connecting to Mikrotik API on {self.device.ip_address}: {e}")
            raise ConnectionError(f"Could not connect to {self.device.device_name} API. Check IP/Port and credentials.") from e

    def get_active_pppoe_users(self):
        """
        Connects via Mikrotik API and retrieves active PPPoE users.
        Returns a list of dictionaries containing user details.
        """
        try:
            api = self._get_api()

            # Access the /ppp/active endpoint
            active_ppp = api.get_resource('/ppp/active')

            # Retrieve all active connections
            users = active_ppp.get()

            # Safely disconnect the pool when done
            self.connection.disconnect()

            return users
        except Exception as e:
            logger.error(
                f"Failed to get active PPPoE users from {self.device.device_name}: {e}")
            return []

    def get_ppp_secrets(self):
        """
        Connects via Mikrotik API and retrieves all PPP secrets.
        Returns a list of dictionaries containing user secrets (profiles, last-logged-out, etc).
        """
        try:
            api = self._get_api()

            # Access the /ppp/secret endpoint
            secrets_api = api.get_resource('/ppp/secret')

            # Retrieve all secrets
            secrets = secrets_api.get()

            # Safely disconnect the pool when done
            self.connection.disconnect()

            return secrets
        except Exception as e:
            logger.error(
                f"Failed to get PPP secrets from {self.device.device_name}: {e}")
            return []

    def remove_active_pppoe_user(self, name):
        """
        Forcibly disconnects an active PPPoE user from the Mikrotik device.
        Useful when a user's status changes to expired or suspended.
        """
        try:
            api = self._get_api()
            active_ppp = api.get_resource('/ppp/active')

            # Find the active session by name
            active_sessions = active_ppp.get(name=name)
            for session in active_sessions:
                active_ppp.remove(id=session['id'])
                logger.info(
                    f"Disconnected active PPPoE user {name} on {self.device.device_name}")

            self.connection.disconnect()
            return True, "User disconnected."
        except Exception as e:
            logger.error(
                f"Failed to disconnect PPPoE user {name} from {self.device.device_name}: {e}")
            return False, f"Mikrotik API Error: {str(e)}"

    def suspend_pppoe_user(self, name):
        """
        Changes a user's profile to 'expired' and drops their active session.
        """
        try:
            api = self._get_api()
            ppp_secret = api.get_resource('/ppp/secret')
            
            # Find the user by name
            secrets = ppp_secret.get(name=name)
            if not secrets:
                return False, f"User {name} not found on MikroTik."
                
            user_id = secrets[0]['id']
            ppp_secret.set(id=user_id, profile="expired")
            logger.info(f"Changed profile for PPPoE user {name} to 'expired'")
            
            # Use existing method to drop active session
            self.remove_active_pppoe_user(name)
            
            # Note: remove_active_pppoe_user might close the connection, 
            # but since it's the last action, it's fine.
            return True, "User suspended and disconnected."
        except Exception as e:
            logger.error(f"Failed to suspend user {name}: {e}")
            return False, f"Mikrotik API Error: {str(e)}"

    def add_pppoe_user(self, name, password, profile, service="pppoe"):
        """
        Creates a PPPoE user (secret) on the Mikrotik device.
        """
        try:
            api = self._get_api()
            secrets = api.get_resource('/ppp/secret')

            # Check if user already exists
            existing = secrets.get(name=name)
            if existing:
                secrets.set(
                    id=existing[0]['id'], password=password, profile=profile, service=service)
                logger.info(
                    f"Updated existing PPPoE user {name} on {self.device.device_name}")
            else:
                secrets.add(name=name, password=password,
                            profile=profile, service=service)
                logger.info(
                    f"Added new PPPoE user {name} to {self.device.device_name}")

            self.connection.disconnect()
            return True, "User successfully created/updated on Mikrotik."
        except Exception as e:
            logger.error(
                f"Failed to add PPPoE user {name} to {self.device.device_name}: {e}")
            return False, f"Mikrotik API Error: {str(e)}"

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
        Retrieves live traffic from specified interfaces.
        interface_names: list of interface names
        """
        if not interface_names:
            return []
        try:
            api = self._get_api()
            interfaces_str = ",".join(interface_names)
            interfaces_api = api.get_resource('/interface')
            traffic = interfaces_api.call('monitor-traffic', {
                'interface': interfaces_str,
                'once': ''
            })
            self.connection.disconnect()
            return traffic
        except Exception as e:
            logger.error(f"Failed to get interface traffic from {self.device.device_name}: {e}")
            return []
