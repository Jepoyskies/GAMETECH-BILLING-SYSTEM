import logging
import socket
import routeros_api
from network_manager.models import MikrotikDevice

from django.core.cache import cache
from django.conf import settings
from .dry_run import DryRunConnectionPool
from .read_only import ReadOnlyApiWrapper

logger = logging.getLogger(__name__)

class MikrotikBase:
        def __init__(self, device: MikrotikDevice, dry_run: bool = None, router_mode: str = None):
            self.device = device
            if router_mode:
                self.router_mode = router_mode.lower().strip()
            elif dry_run is not None:
                # dry_run=False means "do not stub the router", i.e. "really
                # connect". It does NOT mean "you may write". That used to read
                # `else "live"`, which handed out full write access to any caller
                # that passed dry_run=False -- overriding a global
                # ROUTER_MODE=read_only. Resolve through the global setting
                # instead, so only an explicit router_mode can grant writes.
                self.router_mode = (
                    "dry_run" if dry_run
                    else getattr(settings, "ROUTER_MODE", "read_only").lower().strip()
                )
            else:
                self.router_mode = getattr(settings, "ROUTER_MODE", "read_only").lower().strip()

            if self.router_mode not in ("dry_run", "read_only", "live"):
                # Unrecognised value: a config mistake, not permission to write.
                self.router_mode = "read_only"

            self.is_dry_run = (self.router_mode == "dry_run")
            self.is_read_only = (self.router_mode == "read_only")

            if self.is_dry_run or (getattr(settings, "ROUTER_DRY_RUN", False) and self.router_mode != "live"):
                dev_name = getattr(device, "device_name", str(getattr(device, "ip_address", "DryRunRouter")))
                logger.info(f"[ROUTER_MODE={self.router_mode}] Stubbed MikrotikAPI initialized for {dev_name}")
                self.connection = DryRunConnectionPool(dev_name)
                self._connection_failed = False
                return

            # Convert port to integer, fallback to standard API port 8728 if missing
            try:
                port = int(device.api_port)
            except (ValueError, TypeError):
                port = 8728

            # Handle empty/None passwords for test routers
            password = device.api_password if device.api_password else ""

            # Set a default timeout for this thread's sockets to prevent infinite hangs
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(2.0)
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
            if self.is_dry_run:
                return self.connection.get_api()

            if getattr(settings, "ROUTER_DRY_RUN", False) and self.is_read_only:
                return ReadOnlyApiWrapper(self.connection.get_api(), self.device.device_name)

            dev_id = getattr(self.device, "id", None) or self.device.ip_address
            cache_key = f"router_unreachable_{dev_id}"
            if cache.get(cache_key):
                raise ConnectionError(f"Router {self.device.device_name} ({self.device.ip_address}) is currently unreachable (cached).")

            if getattr(self, '_connection_failed', False):
                raise ConnectionError(f"Previous connection attempt to {self.device.ip_address} failed, skipping retry.")

            try:
                # First attempt with plaintext_login (RouterOS v6.43+)
                old_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(2.0)
                try:
                    api = self.connection.get_api()
                    cache.delete(cache_key)
                    # Router is healthy again: reset the backoff so a later
                    # outage starts at the short interval instead of inheriting
                    # a 15-minute penalty from a previous one.
                    cache.delete(cache_key + "_n")
                    if self.is_read_only:
                        return ReadOnlyApiWrapper(api, self.device.device_name)
                    return api
                finally:
                    socket.setdefaulttimeout(old_timeout)
            except routeros_api.exceptions.RouterOsApiCommunicationError as e:
                # Only fall back to legacy (challenge-response) auth when the
                # router actually answered and rejected the credentials.
                #
                # Previously ANY communication error triggered a second full
                # connection attempt. For a router that is simply powered off
                # or unplugged, that doubled the wait for nothing -- two
                # socket timeouts, ~15s of dead page, then the same result.
                # A timeout or refused connection tells us nothing about the
                # auth mode, so trip the breaker immediately instead.
                msg = str(e).lower()
                unreachable = any(
                    k in msg for k in (
                        "timed out", "timeout", "refused", "unreachable",
                        "no route to host", "network is unreachable",
                        "connection reset", "broken pipe", "eof",
                    )
                )
                if unreachable:
                    self._connection_failed = True
                    self._trip_breaker(cache_key)
                    logger.error(
                        f"Timeout/Error connecting to Mikrotik API on "
                        f"{self.device.ip_address}: {e}"
                    )
                    raise ConnectionError(
                        f"Could not connect to {self.device.device_name} API. "
                        f"Check IP/Port and credentials."
                    ) from e

                # If the error string contains "invalid user name or password (6)" and we were using plaintext login,
                # it might actually be an older RouterOS version expecting a challenge-response (plaintext_login=False).
                logger.warning(f"Plaintext login failed for {self.device.device_name}, retrying with legacy authentication...")
                
                try:
                    old_timeout = socket.getdefaulttimeout()
                    socket.setdefaulttimeout(2.0)
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
                        api = self.connection.get_api()
                        cache.delete(cache_key)
                        cache.delete(cache_key + "_n")
                        if self.is_read_only:
                            return ReadOnlyApiWrapper(api, self.device.device_name)
                        return api
                    finally:
                        socket.setdefaulttimeout(old_timeout)
                except Exception as retry_e:
                    self._connection_failed = True
                    self._trip_breaker(cache_key)
                    logger.error(f"Legacy Auth Failed for {self.device.device_name}: {retry_e}")
                    raise ConnectionError(f"Could not authenticate to {self.device.device_name} API. Check credentials.") from retry_e

            except Exception as e:
                self._connection_failed = True
                self._trip_breaker(cache_key)
                logger.error(f"Timeout/Error connecting to Mikrotik API on {self.device.ip_address}: {e}")
                raise ConnectionError(f"Could not connect to {self.device.device_name} API. Check IP/Port and credentials.") from e

        def _trip_breaker(self, cache_key):
            """Remember a dead router for progressively longer, and heal on success.

            The TTL used to be a flat 45s. With four routers on a LAN, every
            45 seconds the next page view re-paid a 2s socket timeout per dead
            router, and a page that touched all of them stalled for ~8s. Worse,
            the retry cost fell on a real user waiting for a page.

            These are LAN devices: one that is unreachable stays unreachable
            until someone physically fixes it. So the breaker now escalates
            30s -> 2m -> 5m -> 15m (capped) and resets the moment the router
            answers again, so recovery is still automatic and immediate.
            """
            attempts = (cache.get(cache_key + "_n") or 0) + 1
            cache.set(cache_key + "_n", attempts, 900)
            ttl = min(30 * (2 ** (attempts - 1)) if attempts < 6 else 900, 900)
            cache.set(cache_key, True, ttl)

