import logging
import socket
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

        # Set a default timeout for this thread's sockets to prevent infinite hangs
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(3.0)
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
            socket.setdefaulttimeout(3.0)
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
                socket.setdefaulttimeout(3.0)
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

    def set_pppoe_comment(self, username, comment_text):
        """
        Updates the comment on a PPPoE secret.
        """
        try:
            api = self._get_api()
            ppp_secret = api.get_resource('/ppp/secret')
            users = ppp_secret.get(name=username)
            if users:
                user_id = users[0]['id']
                ppp_secret.set(id=user_id, comment=comment_text)
                self.connection.disconnect()
                return True, "Comment updated"
            return False, "User not found"
        except Exception as e:
            logger.error(f"Error setting comment for {username} on {self.device.device_name}: {e}")
            return False, f"API Error: {str(e)}"
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

    def kick_active_user(self, username):
        """
        Queries /ppp/active using the RouterOS API, finds the entry where name == username,
        and issues a .remove command. This forces the client's modem to immediately redial.
        """
        try:
            api = self._get_api()
            active_ppp = api.get_resource('/ppp/active')

            # Find the active session by name
            active_sessions = active_ppp.get(name=username)
            
            # DEBUG logging for troubleshooting
            print(f"DEBUG: kick_active_user - Found {len(active_sessions)} active sessions for {username}: {active_sessions}")
            logger.info(f"DEBUG: kick_active_user - Found {len(active_sessions)} active sessions for {username}: {active_sessions}")
            
            if not active_sessions:
                self.connection.disconnect()
                return False, f"No active session found for {username}"

            for session in active_sessions:
                # Some API versions return 'id', others might return '.id'
                session_id = session.get('id') or session.get('.id')
                
                print(f"DEBUG: kick_active_user - Attempting to remove session with internal id: {session_id}")
                logger.info(f"DEBUG: kick_active_user - Attempting to remove session with internal id: {session_id}")
                
                if session_id:
                    active_ppp.remove(id=session_id)
                    logger.info(
                        f"Kicked active PPPoE user {username} on {self.device.device_name}")
                else:
                    logger.error(f"Could not find an 'id' or '.id' in session data: {session}")

            self.connection.disconnect()
            return True, "User kicked successfully."
        except Exception as e:
            # DEBUG logging for the exception
            print(f"DEBUG: API Error in kick_active_user: {str(e)}")
            logger.error(
                f"Failed to kick PPPoE user {username} from {self.device.device_name}: {e}")
            return False, f"Mikrotik API Error: {str(e)}"

    def set_user_pppoe_profile(self, username, profile_name):
        """
        Finds the user in /ppp/secret and updates their profile attribute.
        """
        try:
            api = self._get_api()
            ppp_secret = api.get_resource('/ppp/secret')
            
            # Find the user by name
            secrets = ppp_secret.get(name=username)
            
            print(f"DEBUG: set_user_pppoe_profile - Found {len(secrets)} secrets for {username}: {secrets}")
            logger.info(f"DEBUG: set_user_pppoe_profile - Found {len(secrets)} secrets for {username}: {secrets}")
            
            if not secrets:
                self.connection.disconnect()
                return False, f"User {username} not found on MikroTik."
                
            user_id = secrets[0].get('id') or secrets[0].get('.id')
            
            print(f"DEBUG: set_user_pppoe_profile - Attempting to set profile to {profile_name} with internal id: {user_id}")
            logger.info(f"DEBUG: set_user_pppoe_profile - Attempting to set profile to {profile_name} with internal id: {user_id}")
            
            if user_id:
                ppp_secret.set(id=user_id, profile=profile_name)
                logger.info(f"Changed profile for PPPoE user {username} to '{profile_name}'")
            else:
                logger.error(f"Could not find an 'id' or '.id' in secret data: {secrets[0]}")
            
            self.connection.disconnect()
            return True, "User profile updated."
        except Exception as e:
            print(f"DEBUG: API Error in set_user_pppoe_profile: {str(e)}")
            logger.error(f"Failed to set profile for user {username}: {e}")
            return False, f"Mikrotik API Error: {str(e)}"

    def suspend_pppoe_user(self, name):
        """
        Suspends a user using MAC-level bridge dropping.
        If MAC cannot be found, falls back to disabling the PPP secret.
        """
        try:
            api = self._get_api()
            ppp_secret = api.get_resource('/ppp/secret')
            secrets = ppp_secret.get(name=name)
            
            if not secrets:
                self.connection.disconnect()
                return False, f"User {name} not found on MikroTik."
                
            user_id = secrets[0].get('id') or secrets[0].get('.id')
            
            if not user_id:
                self.connection.disconnect()
                return False, "Could not find internal ID for user."

            # 1. Fetch MAC address
            mac = None
            # Import Customer model lazily to avoid circular imports
            from billing.models import Customer
            customer = Customer.objects.filter(pppoe_username=name).first()
            
            if customer and customer.mac_address:
                mac = customer.mac_address
            else:
                # Try to get from active session
                active_ppp = api.get_resource('/ppp/active')
                active_sessions = active_ppp.get(name=name)
                if active_sessions:
                    mac = active_sessions[0].get('caller-id')
                    if mac and customer:
                        customer.mac_address = mac
                        customer.save()

            if mac:
                # Implement MAC-level Bridge Drop (Option C)
                bridge_filter = api.get_resource('/interface/bridge/filter')
                
                # Check if rule already exists to avoid duplicates
                existing_rules = bridge_filter.get(comment=f"Suspended: {name}")
                if not existing_rules:
                    bridge_filter.add(
                        chain="input",
                        **{"src-mac-address": f"{mac}/FF:FF:FF:FF:FF:FF"},
                        **{"mac-protocol": "pppoe-discovery"},
                        action="drop",
                        comment=f"Suspended: {name}"
                    )
                
                # Ensure secret is NOT disabled
                ppp_secret.set(id=user_id, disabled="no")
                logger.info(f"Suspended PPPoE user {name} (MAC Bridge Drop)")
            else:
                # Fallback to Option B if MAC is unknown
                ppp_secret.set(id=user_id, disabled="yes")
                logger.info(f"Suspended PPPoE user {name} (Fallback: PPP Secret Disabled)")
                
            self.connection.disconnect()
            
            # Kick active session
            self.kick_active_user(name)
            
            return True, "User suspended and disconnected."
        except Exception as e:
            logger.error(f"Failed to suspend user {name}: {e}")
            return False, f"Mikrotik API Error: {str(e)}"

    def enable_pppoe_user(self, name):
        """
        Enables a user's PPP secret and removes any MAC-level bridge drops.
        """
        try:
            api = self._get_api()
            ppp_secret = api.get_resource('/ppp/secret')
            secrets = ppp_secret.get(name=name)
            
            if not secrets:
                self.connection.disconnect()
                return False, f"User {name} not found on MikroTik."
                
            user_id = secrets[0].get('id') or secrets[0].get('.id')
            
            if user_id:
                # Ensure PPP secret is enabled
                ppp_secret.set(id=user_id, disabled="no")
                
                # Remove Bridge Filter Drop rules if they exist
                bridge_filter = api.get_resource('/interface/bridge/filter')
                rules = bridge_filter.get(comment=f"Suspended: {name}")
                for rule in rules:
                    rule_id = rule.get('id') or rule.get('.id')
                    if rule_id:
                        bridge_filter.remove(id=rule_id)

                logger.info(f"Enabled PPPoE user {name} (Removed Bridge Drop)")
                self.connection.disconnect()
                return True, "User enabled."
            else:
                self.connection.disconnect()
                return False, "Could not find internal ID for user."
        except Exception as e:
            logger.error(f"Failed to enable user {name}: {e}")
            return False, f"Mikrotik API Error: {str(e)}"

    def delete_pppoe_user(self, name):
        """
        Deletes a PPPoE user from the Mikrotik device.
        """
        try:
            api = self._get_api()
            secrets = api.get_resource('/ppp/secret')

            existing = secrets.get(name=name)
            if not existing:
                self.connection.disconnect()
                return False, f"User {name} does not exist."
            
            # Clean up any MAC-level bridge drop rules just in case they were suspended
            try:
                bridge_filter = api.get_resource('/interface/bridge/filter')
                rules = bridge_filter.get(comment=f"Suspended: {name}")
                for rule in rules:
                    rule_id = rule.get('id') or rule.get('.id')
                    if rule_id:
                        bridge_filter.remove(id=rule_id)
            except Exception as e:
                logger.error(f"Failed to remove bridge filter during user deletion for {name}: {e}")

            user_id = existing[0].get('id') or existing[0].get('.id')
            secrets.remove(id=user_id)
            logger.info(f"Deleted PPPoE user: {name}")
            self.connection.disconnect()
            
            # Kick session if they are currently online
            self.kick_active_user(name)
            return True, "User deleted successfully."
        except Exception as e:
            logger.error(f"Failed to delete user {name}: {e}")
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

    def add_pppoe_user(self, name, password, profile, service="pppoe", disabled="no"):
        """
        Creates or updates a PPPoE user (secret) on the Mikrotik device.
        """
        try:
            api = self._get_api()
            secrets = api.get_resource('/ppp/secret')

            # Check if user already exists
            existing = secrets.get(name=name)
            if existing:
                secrets.set(
                    id=existing[0]['id'], password=password, profile=profile, service=service, disabled=disabled)
                logger.info(
                    f"Updated existing PPPoE user {name} on {self.device.device_name}")
            else:
                secrets.add(name=name, password=password,
                            profile=profile, service=service, disabled=disabled)
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
