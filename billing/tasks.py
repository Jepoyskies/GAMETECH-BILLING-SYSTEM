import logging
from celery import shared_task
from django.core.management import call_command
from django.core.cache import cache

logger = logging.getLogger(__name__)

@shared_task(name="billing.tasks.auto_suspend_task")
def auto_suspend_task():
    logger.info("Starting auto-suspend task via Celery...")
    try:
        call_command('auto_suspend')
        logger.info("Auto-suspend task completed successfully.")
    except Exception as e:
        logger.error(f"Error in auto-suspend task: {e}")

@shared_task(name="billing.tasks.auto_sms_task")
def auto_sms_task():
    logger.info("Starting auto-SMS task via Celery...")
    try:
        call_command('auto_sms')
        logger.info("Auto-SMS task completed successfully.")
    except Exception as e:
        logger.error(f"Error in auto-SMS task: {e}")

@shared_task(name="billing.tasks.auto_sync_failed_task")
def auto_sync_failed_task():
    logger.info("Starting auto-sync-failed task via Celery...")
    try:
        call_command('auto_sync_failed')
        logger.info("Auto-sync-failed task completed successfully.")
    except Exception as e:
        logger.error(f"Error in auto-sync-failed task: {e}")

@shared_task(name="billing.tasks.auto_reconcile_routers_task")
def auto_reconcile_routers_task():
    logger.info("Starting auto-reconcile-routers task via Celery...")
    try:
        call_command('auto_reconcile_routers')
        logger.info("Auto-reconcile-routers task completed successfully.")
    except Exception as e:
        logger.error(f"Error in auto-reconcile-routers task: {e}")

@shared_task(name="billing.tasks.fetch_live_monitoring_data_task")
def fetch_live_monitoring_data_task():
    logger.info("Starting fetch-live-monitoring data task...")
    try:
        from network_manager.models import MikrotikDevice
        from billing.models import Customer
        from network_manager.services import MikrotikAPI
        
        response_data = {
            'users': [],
            'routers': [],
            'offline_users': [],
            'total_active_subs': 0
        }
        
        devices = MikrotikDevice.objects.all()
        for device in devices:
            try:
                api = MikrotikAPI(device)
                active_users = api.get_active_pppoe_users()
                
                # Fetch active customers from DB
                active_db_customers = Customer.objects.filter(
                    status='active', 
                    mikrotik_device=device
                ).exclude(pppoe_username__isnull=True).exclude(pppoe_username='')
                
                response_data['total_active_subs'] += active_db_customers.count()
                
                # Fetch traffic for all active PPPoE users directly from their dynamic interfaces
                interface_names = [f"<pppoe-{au.get('name')}>" for au in active_users if au.get('name')]
                traffic_data = api.get_interfaces_traffic(interface_names)
                
                # Map traffic data by clean username
                traffic_dict = {}
                for t in traffic_data:
                    name = t.get('name', '')
                    # Strip `<pppoe-` prefix and `>` suffix
                    clean_name = name.strip('<>').replace('pppoe-', '', 1)
                    
                    try:
                        rx_bps = int(t.get('rx-bits-per-second', 0))
                        tx_bps = int(t.get('tx-bits-per-second', 0))
                        rx_mbps = round(rx_bps / 1000000, 2)
                        tx_mbps = round(tx_bps / 1000000, 2)
                        traffic_dict[clean_name] = {
                            'rx_mbps': rx_mbps,
                            'tx_mbps': tx_mbps
                        }
                    except Exception:
                        continue
                        
                for au in active_users:
                    username = au.get('name')
                    tr = traffic_dict.get(username, {'rx_mbps': 0.0, 'tx_mbps': 0.0})
                    response_data['users'].append({
                        'user': username,
                        'ip': au.get('address', ''),
                        'uptime': au.get('uptime', '0s'),
                        'rx_mbps': tr['rx_mbps'],
                        'tx_mbps': tr['tx_mbps'],
                        'device_ip': device.ip_address
                    })
                    
                api.connection.disconnect()
            except Exception as e:
                logger.error(f"Error connecting to Mikrotik {device.device_name}: {e}")
                
        # Save to cache
        cache.set('live_monitoring_data', response_data, timeout=30)
        logger.info("Live-monitoring data cached successfully.")
    except Exception as e:
        logger.error(f"Error in fetch-live-monitoring data task: {e}")
