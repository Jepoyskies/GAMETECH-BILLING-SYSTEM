import csv
import io
import os
import datetime
from django.core.management.base import BaseCommand
from billing.models import Customer, SubscriptionPlan, AccountType

from network_manager.models import MikrotikDevice
from django.utils.dateparse import parse_datetime, parse_date
from django.utils.timezone import make_aware


class Command(BaseCommand):
    help = 'Migrates legacy data from gametech sql dump'

    def add_arguments(self, parser):
        parser.add_argument('sql_file', type=str,
                            help='Path to the SQL dump file')

    def parse_sql_line(self, line):
        line = line.strip()
        if line.startswith('('):
            line = line[1:]
        if line.endswith(');'):
            line = line[:-2]
        elif line.endswith('),'):
            line = line[:-2]

        # Parse as CSV row
        reader = csv.reader(io.StringIO(
            line), quotechar="'", skipinitialspace=True)
        try:
            row = next(reader)
        except StopIteration:
            return []

        # Convert 'NULL' string to None
        return [None if col == 'NULL' else col for col in row]

    def parse_datetime_safe(self, dt_str):
        if not dt_str or dt_str.upper() == 'NULL' or dt_str == '0000-00-00 00:00:00':
            return None
        dt = parse_datetime(dt_str)
        if dt and dt.tzinfo is None:
            return make_aware(dt)
        return dt

    def parse_date_safe(self, d_str):
        if not d_str or d_str.upper() == 'NULL' or d_str == '0000-00-00':
            return None
        return parse_date(d_str)

    def handle(self, *args, **kwargs):
        sql_file_path = kwargs['sql_file']

        if not os.path.exists(sql_file_path):
            self.stdout.write(self.style.ERROR(
                f'File "{sql_file_path}" does not exist.'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Reading from {sql_file_path} ...'))

        current_table = None

        # Tracking for FKs
        plan_map = {}
        device_map = {}
        account_type_map = {}

        with open(sql_file_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                if line.startswith('INSERT INTO `mikrotik_devices`'):
                    current_table = 'mikrotik_devices'
                    continue
                elif line.startswith('INSERT INTO `service_plans`'):
                    current_table = 'service_plans'
                    continue
                elif line.startswith('INSERT INTO `customers`'):
                    current_table = 'customers'
                    continue
                elif line.startswith('INSERT INTO `account_type`'):
                    current_table = 'account_type'
                    continue
                elif line.startswith('INSERT INTO'):
                    current_table = None
                    continue

                if not current_table:
                    continue

                if not line.strip().startswith('('):
                    # End of insert block or empty line
                    if line.strip() == '' or line.strip().startswith('--') or line.strip().startswith('/*!'):
                        pass
                    else:
                        current_table = None
                    continue

                row = self.parse_sql_line(line)
                if not row:
                    continue

                if current_table == 'mikrotik_devices' and len(row) >= 6:
                    device_name = row[1]
                    ip_address = row[2]
                    try:
                        obj, created = MikrotikDevice.objects.get_or_create(
                            ip_address=ip_address,
                            defaults={
                                'device_name': device_name,
                                'api_username': row[3],
                                'api_password': row[4],
                                'api_port': row[5],
                            }
                        )
                        device_map[device_name] = obj
                        if created:
                            self.stdout.write(
                                f'Created MikrotikDevice: {device_name}')
                    except Exception as e:
                        self.stderr.write(
                            f'Error MikrotikDevice {device_name}: {e}')

                elif current_table == 'account_type' and len(row) >= 2:
                    type_name = row[1]
                    try:
                        obj, created = AccountType.objects.get_or_create(
                            type_name=type_name)
                        account_type_map[type_name] = obj
                        if created:
                            self.stdout.write(
                                f'Created AccountType: {type_name}')
                    except Exception as e:
                        self.stderr.write(
                            f'Error AccountType {type_name}: {e}')

                elif current_table == 'service_plans' and len(row) >= 13:
                    plan_name = row[2]
                    try:
                        obj, created = SubscriptionPlan.objects.get_or_create(
                            name=plan_name,
                            defaults={
                                'speed_up': str(row[3]) if row[3] else '',
                                'speed_down': str(row[4]) if row[4] else '',
                                'price': row[5] or 0.00,
                                'validity_days': int(row[11]) if row[11] else 30,
                                'description': row[12],
                            }
                        )
                        plan_map[plan_name] = obj
                        if created:
                            self.stdout.write(
                                f'Created SubscriptionPlan: {plan_name}')
                    except Exception as e:
                        self.stderr.write(
                            f'Error SubscriptionPlan {plan_name}: {e}')

                elif current_table == 'customers' and len(row) >= 27:
                    username = row[1]
                    full_name = row[5]
                    email = row[6] if row[6] else None
                    if email == '':
                        email = None

                    acct_type_str = row[2]
                    plan_name_str = row[3]
                    device_name_str = row[16]

                    acct_obj = account_type_map.get(acct_type_str)
                    if not acct_obj and acct_type_str:
                        acct_obj = AccountType.objects.filter(
                            type_name=acct_type_str).first()
                        if acct_obj:
                            account_type_map[acct_type_str] = acct_obj

                    plan_obj = plan_map.get(plan_name_str)
                    if not plan_obj and plan_name_str:
                        plan_obj = SubscriptionPlan.objects.filter(
                            name=plan_name_str).first()
                        if plan_obj:
                            plan_map[plan_name_str] = plan_obj

                    device_obj = device_map.get(device_name_str)
                    if not device_obj and device_name_str:
                        device_obj = MikrotikDevice.objects.filter(
                            device_name=device_name_str).first()
                        if device_obj:
                            device_map[device_name_str] = device_obj

                    expires_at = self.parse_datetime_safe(row[4])
                    if not expires_at:
                        expires_at = make_aware(datetime.datetime.now())

                    try:
                        defaults = {
                            'account_type': acct_obj,
                            'plan': plan_obj,
                            'mikrotik_device': device_obj,
                            'expires_at': expires_at,
                            'full_name': full_name,
                            'phone': row[7],
                            'address': row[8],
                            'status': row[9] if row[9] else CustomerStatus.ACTIVE,
                            'created_at': self.parse_datetime_safe(row[10]) or make_aware(datetime.datetime.now()),
                            'latitude': float(row[11]) if row[11] else None,
                            'longitude': float(row[12]) if row[12] else None,
                            'adjusted_by_router': row[13],
                            'adjusted_by_referral': row[14],
                            'last_expiry_sms_sent': self.parse_datetime_safe(row[15]),
                            'sms_sent_at': self.parse_datetime_safe(row[17]),
                            'mac_address': row[18],
                            'agent': row[19],
                            'referral_received': row[20] if row[20] else '',
                            'last_sms_due': self.parse_datetime_safe(row[21]),
                            'connection': row[22] if row[22] else '',
                            'created_form_by': row[23] if row[23] else '',
                            'cignalplay_no': row[24],
                            'cignalplay_date': self.parse_date_safe(row[25]),
                            'cignalplay_adjustedby': row[26]
                        }

                        if username:
                            defaults['email'] = email
                            customer, created = Customer.objects.get_or_create(
                                pppoe_username=username, defaults=defaults)
                        else:
                            defaults['pppoe_username'] = username
                            customer, created = Customer.objects.get_or_create(
                                full_name=full_name, email=email, defaults=defaults)

                        if created:
                            self.stdout.write(
                                f'Created Customer: {username or full_name}')
                    except Exception as e:
                        self.stderr.write(
                            f'Error Customer {username or full_name}: {e}')

        self.stdout.write(self.style.SUCCESS('Migration complete!'))
