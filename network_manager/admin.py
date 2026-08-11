from django.contrib import admin
from .models import MikrotikDevice

@admin.register(MikrotikDevice)
class MikrotikDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_name', 'ip_address', 'api_username', 'api_port')
    search_fields = ('device_name', 'ip_address')
    list_filter = ('api_port',)
