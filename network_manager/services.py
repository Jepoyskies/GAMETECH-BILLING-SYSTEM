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

        # We set up the API connection pool
        self.connection = routeros_api.RouterOsApiPool(
            host=device.ip_address,
            username=device.api_username,
            password=device.api_password,
            port=port,
            plaintext_login=True, # Modern RouterOS versions use plain login sequence for API
            use_ssl=False  # Set to True if using secure port (e.g., 8729)
        )

    def _get_api(self):
        """Handles connection securely with timeouts and returns the API instance."""
        try:
            # get_api() will attempt connection. The library handles socket timeouts natively.
            api = self.connection.get_api()
            return api
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
            logger.error(f"Failed to get active PPPoE users from {self.device.device_name}: {e}")
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
                logger.info(f"Disconnected active PPPoE user {name} on {self.device.device_name}")
                
            self.connection.disconnect()
            return True, "User disconnected."
        except Exception as e:
            logger.error(f"Failed to disconnect PPPoE user {name} from {self.device.device_name}: {e}")
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
                secrets.set(id=existing[0]['id'], password=password, profile=profile, service=service)
                logger.info(f"Updated existing PPPoE user {name} on {self.device.device_name}")
            else:
                secrets.add(name=name, password=password, profile=profile, service=service)
                logger.info(f"Added new PPPoE user {name} to {self.device.device_name}")
                
            self.connection.disconnect()
            return True, "User successfully created/updated on Mikrotik."
        except Exception as e:
            logger.error(f"Failed to add PPPoE user {name} to {self.device.device_name}: {e}")
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
            logger.error(f"Failed to get simple queues from {self.device.device_name}: {e}")
            return []
