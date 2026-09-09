import logging
import socket
import routeros_api
from .models import MikrotikDevice

logger = logging.getLogger(__name__)

class MikrotikSecretsMixin:
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

        def delete_ppp_secret(self, internal_id):
            try:
                api = self._get_api()
                secrets = api.get_resource('/ppp/secret')
                secrets.remove(id=internal_id)
                self.connection.disconnect()
                return True, "Secret deleted successfully."
            except Exception as e:
                logger.error(f"Failed to delete PPP secret {internal_id} on {self.device.device_name}: {e}")
                return False, str(e)

        def update_ppp_secret(self, internal_id, **kwargs):
            try:
                api = self._get_api()
                secrets = api.get_resource('/ppp/secret')
                secrets.set(id=internal_id, **kwargs)
                self.connection.disconnect()
                return True, "Secret updated successfully."
            except Exception as e:
                logger.error(f"Failed to update PPP secret {internal_id} on {self.device.device_name}: {e}")
                return False, str(e)

