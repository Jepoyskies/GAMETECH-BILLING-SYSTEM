from django.contrib import admin
from .models import MikrotikDevice, NapBox


@admin.register(MikrotikDevice)
class MikrotikDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_name', 'ip_address', 'api_username', 'api_port')
    search_fields = ('device_name', 'ip_address')
    list_filter = ('api_port',)


@admin.register(NapBox)
class NapBoxAdmin(admin.ModelAdmin):
    list_display = ('napbox_no', 'latitude', 'longitude', 'marker_color', 'created_at')
    search_fields = ('napbox_no',)
    list_filter = ('marker_color',)
