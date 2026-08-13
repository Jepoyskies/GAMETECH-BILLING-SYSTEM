from django.db import models


class MikrotikDevice(models.Model):
    device_name = models.CharField(max_length=255, unique=True)
    ip_address = models.GenericIPAddressField()
    api_username = models.CharField(max_length=255)
    api_password = models.CharField(max_length=255)
    api_port = models.IntegerField(default=8728)
    api_port_8700 = models.IntegerField(default=8700)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.device_name


class NapBox(models.Model):
    napbox_no = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    marker_color = models.CharField(max_length=20, default='red')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.napbox_no
