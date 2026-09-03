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

@shared_task(name="billing.tasks.auto_process_sla_rebates")
def auto_process_sla_rebates():
    logger.info("Starting SLA auto-rebate task...")
    try:
        from dispatch.models import DispatchRecord
        from billing.models import Rebate, Customer
        import datetime
        from django.utils import timezone
        
        open_tickets = DispatchRecord.objects.filter(
            done_at__isnull=True,
            customer__isnull=False
        )
        
        rebates_issued = 0
        
        for ticket in open_tickets:
            delta = timezone.now() - ticket.created_at
            hours_open = delta.total_seconds() / 3600
            
            if hours_open >= 24:
                owed_days = int(hours_open // 24)
                if owed_days > ticket.sla_rebates_given:
                    days_to_add = owed_days - ticket.sla_rebates_given
                    customer = ticket.customer
                    
                    if customer.expires_at:
                        old_expiry = customer.expires_at
                        new_expiry = old_expiry + datetime.timedelta(days=days_to_add)
                        customer.expires_at = new_expiry
                        customer.save()
                        
                        Rebate.objects.create(
                            customer=customer,
                            username=customer.pppoe_username,
                            plan_name=customer.plan.name if customer.plan else None,
                            current_expiry=old_expiry,
                            expires_at=new_expiry,
                            amount=0,
                            note=f"Auto SLA Rebate: Ticket #{ticket.id} open > {owed_days*24} hours",
                            adjusted_by="System"
                        )
                        
                        ticket.sla_rebates_given = owed_days
                        ticket.save()
                        rebates_issued += 1
                        
                        # Send Notification
                        from billing.models import MessageTemplate, Notification
                        import requests
                        from django.conf import settings
                        from django.core.mail import send_mail
                        
                        context = {
                            '{customer_name}': customer.full_name or customer.pppoe_username,
                            '{paid_amount}': '0.00', # Re-use placeholder for consistency
                            '{new_expiration}': new_expiry.strftime('%B %d, %Y'),
                            '{days_added}': str(days_to_add)
                        }
                        
                        # Try to find an SLA Rebate SMS template, or fallback to Payment Success logic but altered
                        template_sms = MessageTemplate.objects.filter(type='SMS', name__icontains='SLA').first()
                        if not template_sms:
                            template_sms = MessageTemplate.objects.filter(type='SMS').first() # fallback
                            
                        if template_sms and customer.phone:
                            sms_msg = template_sms.body if 'SLA' in template_sms.name else f"Hello {customer.full_name}, an SLA Rebate of {days_to_add} days has been added to your account for ticket #{ticket.id}. New expiry: {new_expiry.strftime('%b %d, %Y')}."
                            for k, v in context.items():
                                sms_msg = sms_msg.replace(k, v)
                                
                            try:
                                semaphore_api = getattr(settings, 'SEMAPHORE_API_KEY', '')
                                if semaphore_api:
                                    requests.post('https://api.semaphore.co/api/v4/messages', data={
                                        'apikey': semaphore_api,
                                        'number': customer.phone,
                                        'message': sms_msg,
                                        'sendername': getattr(settings, 'SEMAPHORE_SENDER_NAME', '')
                                    }, timeout=5)
                                    from billing.models import SmsLog
                                    SmsLog.objects.create(
                                        customer=customer,
                                        phone_number=customer.phone,
                                        message=sms_msg,
                                        status='Sent',
                                        api_response='Sent via SLA Task'
                                    )
                            except Exception as e:
                                logger.error(f"Failed to send SLA SMS to {customer.phone}: {e}")
                                
                        # Try to find an SLA Rebate Email template
                        template_email = MessageTemplate.objects.filter(type='EMAIL', name__icontains='SLA').first()
                        if not template_email:
                            template_email = MessageTemplate.objects.filter(type='EMAIL').first() # fallback
                            
                        if template_email and customer.email:
                            subj = template_email.subject if 'SLA' in template_email.name else 'SLA Rebate Applied'
                            msg = template_email.body if 'SLA' in template_email.name else f"Hello {customer.full_name},\n\nAn SLA Rebate of {days_to_add} days has been added to your account for ticket #{ticket.id}.\nNew expiry: {new_expiry.strftime('%B %d, %Y')}.\n\nThank you!"
                            for k, v in context.items():
                                msg = msg.replace(k, v)
                            
                            try:
                                send_mail(
                                    subj,
                                    msg,
                                    settings.DEFAULT_FROM_EMAIL,
                                    [customer.email],
                                    fail_silently=True
                                )
                            except Exception as e:
                                logger.error(f"Failed to send SLA Email to {customer.email}: {e}")
                                
                        # System Notification
                        Notification.objects.create(
                            user=None,
                            customer=customer,
                            message=f"SLA Rebate applied: {days_to_add} days added. Ticket #{ticket.id}.",
                            notification_type="System"
                        )
                        
        logger.info(f"SLA auto-rebate task completed. Issued {rebates_issued} rebates.")
    except Exception as e:
        logger.error(f"Error in SLA auto-rebate task: {e}")

@shared_task(name="billing.tasks.check_service_status_task")
def check_service_status_task():
    logger.info("Starting Downdetector service status check...")
    try:
        from billing.models import MonitoredService
        import subprocess
        import platform
        from django.utils import timezone
        
        services = MonitoredService.objects.all()
        for service in services:
            hostname = service.url.replace("https://", "").replace("http://", "").split("/")[0]
            
            # Cross-platform ping command
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            command = ['ping', param, '1', hostname]
            
            try:
                # Run ping command with timeout
                output = subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=5).decode()
                
                # Check for successful response
                if ('TTL=' in output) or ('ttl=' in output):
                    service.status = 'Online'
                    
                    # Extract latency (roughly)
                    if platform.system().lower() == 'windows':
                        try:
                            # Average = 12ms
                            ms = output.split('Average = ')[1].split('ms')[0].strip()
                            service.latency_ms = int(ms)
                        except:
                            service.latency_ms = 0
                    else:
                        try:
                            # time=12.3 ms
                            ms = output.split('time=')[1].split(' ms')[0].strip()
                            service.latency_ms = float(ms)
                        except:
                            service.latency_ms = 0
                else:
                    service.status = 'Offline'
                    service.latency_ms = 0
                    
            except subprocess.TimeoutExpired:
                service.status = 'Timeout'
                service.latency_ms = 0
            except Exception:
                service.status = 'Offline'
                service.latency_ms = 0
                
            service.last_checked = timezone.now()
            service.save()
            
        logger.info("Downdetector service status check completed.")
    except Exception as e:
        logger.error(f"Error in Downdetector check task: {e}")
