import logging
from celery import shared_task
from django.core.management import call_command

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
