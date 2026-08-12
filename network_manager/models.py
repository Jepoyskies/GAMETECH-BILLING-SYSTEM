from django.db import models

class MikrotikDevice(models.Model):
    device_name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    api_username = models.CharField(max_length=50)
    api_password = models.CharField(max_length=50, blank=True, null=True)
    api_port = models.CharField(max_length=50)
    api_port_8700 = models.CharField(max_length=50, blank=True, null=True, default='8700')

    def __str__(self):
        return f"{self.device_name} ({self.ip_address})"
