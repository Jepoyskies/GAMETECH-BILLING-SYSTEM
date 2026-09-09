import logging
import socket
import routeros_api
from .models import MikrotikDevice

logger = logging.getLogger(__name__)

class MikrotikProfilesMixin:
        def get_ppp_profiles(self):
            try:
                api = self._get_api()
                profiles = api.get_resource('/ppp/profile').get()
                self.connection.disconnect()
                return profiles
            except Exception as e:
                logger.error(f"Failed to get PPP profiles from {self.device.device_name}: {e}")
                return []

        def delete_ppp_profile(self, internal_id):
            try:
                api = self._get_api()
                profiles = api.get_resource('/ppp/profile')
                profiles.remove(id=internal_id)
                self.connection.disconnect()
                return True, "Profile deleted successfully."
            except Exception as e:
                logger.error(f"Failed to delete PPP profile {internal_id} on {self.device.device_name}: {e}")
                return False, str(e)

        def add_ppp_profile(self, **kwargs):
            try:
                api = self._get_api()
                profiles = api.get_resource('/ppp/profile')
                profiles.add(**kwargs)
                self.connection.disconnect()
                return True, "Profile added successfully."
            except Exception as e:
                logger.error(f"Failed to add PPP profile on {self.device.device_name}: {e}")
                return False, str(e)

        def update_ppp_profile(self, internal_id, **kwargs):
            try:
                api = self._get_api()
                profiles = api.get_resource('/ppp/profile')
                profiles.set(id=internal_id, **kwargs)
                self.connection.disconnect()
                return True, "Profile updated successfully."
            except Exception as e:
                logger.error(f"Failed to update PPP profile {internal_id} on {self.device.device_name}: {e}")
                return False, str(e)

        def sync_plan_to_mikrotik(self, plan_name, speed_up, speed_down):
            """
            Creates or updates a /ppp/profile on the Mikrotik router based on the Django SubscriptionPlan.
            Converts human readable speeds like '10 Mbps' to '10M/10M'.
            """
            import re
            
            # Helper to convert "10 Mbps" or "10Mbps" to "10M"
            def parse_speed(speed_str):
                if not speed_str:
                    return "1M" # fallback
                s = speed_str.lower().strip()
                # Extract number
                match = re.search(r'(\d+)', s)
                if not match:
                    return "1M"
                num = match.group(1)
                if 'k' in s:
                    return f"{num}k"
                elif 'g' in s:
                    return f"{num}G"
                return f"{num}M"
                
            rate_limit = f"{parse_speed(speed_up)}/{parse_speed(speed_down)}"
            
            try:
                api = self._get_api()
                profiles = api.get_resource('/ppp/profile')
                existing = profiles.get(name=plan_name)
                
                if existing:
                    prof_id = existing[0].get('id') or existing[0].get('.id')
                    profiles.set(id=prof_id, **{'rate-limit': rate_limit})
                    logger.info(f"Updated MikroTik profile '{plan_name}' to {rate_limit}")
                else:
                    # Basic profile creation
                    profiles.add(
                        name=plan_name,
                        **{'local-address': '100.64.224.1'}, # standard internal routing ip used in other profiles
                        **{'remote-address': 'pppoe-pool'}, 
                        **{'rate-limit': rate_limit}
                    )
                    logger.info(f"Created MikroTik profile '{plan_name}' at {rate_limit}")
                self.connection.disconnect()
                return True, "Profile synced successfully"
            except Exception as e:
                logger.error(f"Failed to sync profile {plan_name}: {e}")
                return False, str(e)

        def delete_plan_from_mikrotik(self, plan_name):
            """
            Deletes a /ppp/profile on the Mikrotik router.
            """
            try:
                api = self._get_api()
                profiles = api.get_resource('/ppp/profile')
                existing = profiles.get(name=plan_name)
                
                if existing:
                    prof_id = existing[0].get('id') or existing[0].get('.id')
                    profiles.remove(id=prof_id)
                    logger.info(f"Deleted MikroTik profile '{plan_name}'")
                self.connection.disconnect()
                return True, "Profile deleted successfully"
            except Exception as e:
                logger.error(f"Failed to delete profile {plan_name}: {e}")
                return False, str(e)

