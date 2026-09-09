import logging
import socket
import routeros_api
from .models import MikrotikDevice

logger = logging.getLogger(__name__)

class MikrotikUsersMixin:
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
                            Customer.objects.filter(pk=customer.pk).update(mac_address=mac)

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

        def add_pppoe_user(self, name, password, profile, service="pppoe", disabled="no", comment=None):
            """
            Creates or updates a PPPoE user (secret) on the Mikrotik device.
            """
            try:
                api = self._get_api()
                
                # First, ensure the profile exists on the router to avoid rejection
                profile_api = api.get_resource('/ppp/profile')
                if not profile_api.get(name=profile):
                    profile_api.add(name=profile)
                    logger.info(f"Auto-created missing PPPoE Profile '{profile}' on {self.device.device_name}")
                    
                secrets = api.get_resource('/ppp/secret')

                # Check if user already exists
                existing = secrets.get(name=name)
                if existing:
                    update_params = {
                        'id': existing[0].get('id') or existing[0].get('.id'),
                        'password': password,
                        'profile': profile,
                        'service': service,
                        'disabled': disabled
                    }
                    if comment:
                        update_params['comment'] = comment
                    
                    secrets.set(**update_params)
                    logger.info(
                        f"Updated existing PPPoE user {name} on {self.device.device_name}")
                else:
                    add_params = {
                        'name': name,
                        'password': password,
                        'profile': profile,
                        'service': service,
                        'disabled': disabled
                    }
                    if comment:
                        add_params['comment'] = comment
                        
                    secrets.add(**add_params)
                    logger.info(
                        f"Added new PPPoE user {name} to {self.device.device_name}")

                self.connection.disconnect()
                return True, "User successfully created/updated on Mikrotik."
            except Exception as e:
                logger.error(
                    f"Failed to add PPPoE user {name} to {self.device.device_name}: {e}")
                return False, f"Mikrotik API Error: {str(e)}"

