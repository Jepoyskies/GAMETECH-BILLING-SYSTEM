import logging
import socket
import routeros_api

logger = logging.getLogger(__name__)

class MikrotikAPI:
    """
    Dedicated API service for the 2-Way Sync Staging Area.
    This class handles raw credentials and strictly returns safe dictionaries.
    """

    def __init__(self, ip_address, username, password, port):
        self.ip_address = ip_address
        self.username = username
        self.password = password
        
        try:
            self.port = int(port)
        except (ValueError, TypeError):
            self.port = 8728

    def _get_api_connection(self):
        """Helper to get a fresh connection to the router."""
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(5.0)
        try:
            connection = routeros_api.RouterOsApiPool(
                host=self.ip_address,
                username=self.username,
                password=self.password,
                port=self.port,
                plaintext_login=True,
                use_ssl=False
            )
            api = connection.get_api()
            return connection, api
        except routeros_api.exceptions.RouterOsApiCommunicationError:
            # Fallback for legacy authentication
            try:
                connection = routeros_api.RouterOsApiPool(
                    host=self.ip_address,
                    username=self.username,
                    password=self.password,
                    port=self.port,
                    plaintext_login=False,
                    use_ssl=False
                )
                api = connection.get_api()
                return connection, api
            except Exception as e:
                raise ConnectionError(f"Authentication failed: {str(e)}")
        finally:
            socket.setdefaulttimeout(old_timeout)

    def get_all_pppoe_users(self):
        """
        Get Users (For Import): Returns a list of dictionaries containing name, password, profile, and comment.
        """
        try:
            connection, api = self._get_api_connection()
            secrets_api = api.get_resource('/ppp/secret')
            secrets = secrets_api.get()
            connection.disconnect()
            
            # Format the output to strictly match requirements
            formatted_users = []
            for s in secrets:
                formatted_users.append({
                    "name": s.get("name", ""),
                    "password": s.get("password", ""),
                    "profile": s.get("profile", ""),
                    "comment": s.get("comment", "")
                })
                
            return {"success": True, "data": formatted_users}
        except Exception as e:
            logger.error(f"Error in get_all_pppoe_users: {e}")
            return {"success": False, "error": str(e)}

    def add_pppoe_user(self, name, password, profile, comment):
        """
        Push User (For Export): Creates or updates a user on the router.
        """
        try:
            connection, api = self._get_api_connection()
            secrets_api = api.get_resource('/ppp/secret')
            
            existing = secrets_api.get(name=name)
            if existing:
                # Update existing
                user_id = existing[0].get('id') or existing[0].get('.id')
                secrets_api.set(
                    id=user_id,
                    password=password,
                    profile=profile,
                    comment=comment
                )
                msg = f"User {name} updated successfully."
            else:
                # Add new
                secrets_api.add(
                    name=name,
                    password=password,
                    profile=profile,
                    comment=comment,
                    service="pppoe"
                )
                msg = f"User {name} created successfully."
                
            connection.disconnect()
            return {"success": True, "message": msg}
        except Exception as e:
            logger.error(f"Error in add_pppoe_user: {e}")
            return {"success": False, "error": str(e)}

    def delete_pppoe_user(self, name):
        """
        Delete User (For Cleanup): Finds and removes an orphaned user from the router.
        """
        try:
            connection, api = self._get_api_connection()
            secrets_api = api.get_resource('/ppp/secret')
            
            existing = secrets_api.get(name=name)
            if existing:
                user_id = existing[0].get('id') or existing[0].get('.id')
                secrets_api.remove(id=user_id)
                msg = f"User {name} deleted successfully."
            else:
                msg = f"User {name} not found."
                
            connection.disconnect()
            return {"success": True, "message": msg}
        except Exception as e:
            logger.error(f"Error in delete_pppoe_user: {e}")
            return {"success": False, "error": str(e)}
