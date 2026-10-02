import logging
import socket
import routeros_api
from django.conf import settings
from network_manager.services.dry_run import DryRunConnectionPool

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
        """Helper to get a fresh connection to the router.

        This is a SECOND, independent connection path from
        `network_manager.services.MikrotikAPI`, and it used to have none of the
        protections: no circuit breaker, a 5s socket timeout, and a legacy-auth
        retry on any error. Opening the Sync Manager on a powered-off router
        therefore blocked for ~15s every single time (two 5s timeouts plus
        library retries), which reads as a broken site.

        It now shares the same breaker, the same LAN-sized timeout, and the
        same rule: only retry legacy auth when the router ANSWERED and rejected
        the credentials. A timeout means it is unreachable, and no auth mode
        will change that.
        """
        mode = getattr(settings, "ROUTER_MODE", "live").lower().strip()
        if mode == "dry_run" or (getattr(settings, "ROUTER_DRY_RUN", False) and mode != "live"):
            pool = DryRunConnectionPool(self.ip_address)
            return pool, pool.get_api()

        from django.core.cache import cache

        # Share ONE breaker key with services/base.py, which keys on the device
        # id. This class is constructed from raw credentials with no device
        # object, so resolve the id from the IP -- otherwise the two paths keep
        # separate opinions about which routers are down and neither trip the
        # other's breaker.
        dev = getattr(self, "device", None)
        if dev is None:
            try:
                from network_manager.models import MikrotikDevice
                dev = MikrotikDevice.objects.filter(ip_address=self.ip_address).first()
            except Exception:
                dev = None
        dev_id = dev.id if dev is not None else self.ip_address
        cache_key = f"router_unreachable_{dev_id}"
        if cache.get(cache_key):
            raise ConnectionError(
                f"Router {self.ip_address} is currently unreachable (cached)."
            )

        def _unreachable(exc):
            msg = str(exc).lower()
            return any(k in msg for k in (
                "timed out", "timeout", "refused", "unreachable",
                "no route to host", "network is unreachable",
                "connection reset", "broken pipe", "eof",
            ))

        def _trip():
            attempts = (cache.get(cache_key + "_n") or 0) + 1
            cache.set(cache_key + "_n", attempts, 900)
            ttl = min(30 * (2 ** (attempts - 1)) if attempts < 6 else 900, 900)
            cache.set(cache_key, True, ttl)

        # These are LAN devices on a private subnet. A dead one stops answering
        # in under a second, so 2s is a generous ceiling and 5s was just making
        # every failure feel like a hang.
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(2.0)
        try:
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
                cache.delete(cache_key)
                cache.delete(cache_key + "_n")
                if mode == "read_only":
                    from network_manager.services.read_only import ReadOnlyApiWrapper
                    api = ReadOnlyApiWrapper(api, self.ip_address)
                return connection, api
            except routeros_api.exceptions.RouterOsApiCommunicationError as e:
                if _unreachable(e):
                    _trip()
                    raise ConnectionError(
                        f"Could not connect to {self.ip_address}. "
                        f"Check IP/Port and credentials."
                    ) from e

                # Fallback for legacy authentication -- only reached when the
                # router replied and rejected the credentials.
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
                    cache.delete(cache_key)
                    cache.delete(cache_key + "_n")
                    if mode == "read_only":
                        from network_manager.services.read_only import ReadOnlyApiWrapper
                        api = ReadOnlyApiWrapper(api, self.ip_address)
                    return connection, api
                except Exception as e:
                    _trip()
                    raise ConnectionError(
                        f"Could not authenticate to {self.ip_address}."
                    ) from e
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
            active_api = api.get_resource('/ppp/active')
            active_users = active_api.get()
            connection.disconnect()
            
            active_usernames = {u.get('name') for u in active_users if u.get('name')}
            
            import re
            # Only allow alphanumeric, dashes, dots, and underscores
            suspicious_pattern = re.compile(r'[^a-zA-Z0-9\.\-\_]')

            # Format the output to strictly match requirements
            formatted_users = []
            secret_usernames = set()
            for s in secrets:
                name = s.get("name", "")
                profile = s.get("profile", "")
                comment = s.get("comment", "")
                secret_usernames.add(name)

                is_active = name in active_usernames

                # `disabled` is the ONE field that tells us whether the old
                # system actually cut this customer off or kept them online.
                # It was never read, so the Sync Manager showed every secret as
                # if it were in the same state and could not answer "is this
                # person connected or suspended?" -- the exact question a
                # collections review needs. MikroTik returns the string
                # "true"/"false", so normalise it.
                raw_disabled = s.get("disabled")
                is_disabled = str(raw_disabled).strip().lower() in ("true", "yes", "1")

                # A user is suspicious if:
                # 1. Name has weird characters
                # 2. Profile is 'default'
                # 3. Comment is empty
                # 4. Comment doesn't contain '|' (which separates Name | Barangay)
                has_weird_chars = bool(suspicious_pattern.search(name))
                is_default_profile = profile.lower() == 'default'
                is_missing_info = not comment or '|' not in comment
                # A secret with no profile and no password can never
                # authenticate, no matter what the comment says.
                is_unusable = not s.get("profile") and not s.get("password")

                suspicious_reasons = []
                if has_weird_chars:
                    suspicious_reasons.append("Invalid Characters")
                if is_default_profile:
                    suspicious_reasons.append("Default Profile")
                if is_missing_info:
                    suspicious_reasons.append("Missing/Invalid Comment")
                if is_unusable:
                    suspicious_reasons.append("No Profile or Password - cannot authenticate")

                is_suspicious = bool(suspicious_reasons)

                formatted_users.append({
                    "name": name,
                    "password": s.get("password", ""),
                    "profile": profile,
                    "comment": comment,
                    # Real state, straight from the router.
                    "disabled": is_disabled,
                    "is_enabled": not is_disabled,
                    "is_active": is_active,
                    "is_suspicious": is_suspicious,
                    "suspicious_reasons": ", ".join(suspicious_reasons)
                })

            # Detect active sessions running without a secret (e.g. transferred to another router without kick)
            for au in active_users:
                aname = au.get("name")
                if aname and aname not in secret_usernames:
                    formatted_users.append({
                        "name": aname,
                        "password": "",
                        "profile": "(Active Session - No Secret)",
                        "comment": f"Active IP: {au.get('address', 'N/A')} | Uptime: {au.get('uptime', 'N/A')}",
                        "is_active": True,
                        "is_suspicious": True,
                        "suspicious_reasons": "Active session with no secret on this router (Transferred or Orphan)",
                    })
                
            return {"success": True, "data": formatted_users}
        except Exception as e:
            logger.error(f"Error in get_all_pppoe_users: {e}")
            return {"success": False, "error": str(e)}

    def add_pppoe_user(self, name, password, profile, comment):
        """
        Push User (For Export): Creates or updates a user on the router.
        """
        mode = getattr(settings, "ROUTER_MODE", "live").lower().strip()
        if mode == "read_only":
            from network_manager.services.read_only import log_blocked_write
            log_blocked_write(f"Blocked sync_services.add_pppoe_user for {name} on {self.ip_address}")
            return {"success": False, "error": "Blocked by read_only mode"}

        # Ensure comment is safe for Mikrotik API
        if comment:
            comment = str(comment).replace('\n', ' ').replace('\r', ' ')
            comment = "".join(c for c in comment if c.isprintable())
            
        try:
            connection, api = self._get_api_connection()
            
            # First, ensure the profile exists on the router to avoid rejection
            profile_api = api.get_resource('/ppp/profile')
            if not profile_api.get(name=profile):
                profile_api.add(name=profile)
                logger.info(f"Auto-created missing PPPoE Profile '{profile}' at {self.ip_address}")
                
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
        mode = getattr(settings, "ROUTER_MODE", "live").lower().strip()
        if mode == "read_only":
            from network_manager.services.read_only import log_blocked_write
            log_blocked_write(f"Blocked sync_services.delete_pppoe_user for {name} on {self.ip_address}")
            return {"success": False, "error": "Blocked by read_only mode"}

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
