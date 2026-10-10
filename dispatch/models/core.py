from django.db import models
from django.contrib.auth.models import User


class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Technician(models.Model):
    name = models.CharField(max_length=100, unique=True)
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    target_per_day = models.IntegerField(default=0)
    target_per_month = models.IntegerField(default=0)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    is_available = models.BooleanField(default=True, help_text="Manual duty-status hint shown in the roster. Does NOT restrict assignment.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name


class ConfigOption(models.Model):
    LIST_TYPE_CHOICES = (
        ('STATUS', 'STATUS'),
        ('TYPE', 'TYPE'),
        ('CHAT_TYPE', 'CHAT_TYPE'),
        ('REPLACEMENT_REASON', 'REPLACEMENT_REASON'),
    )
    MODULE_CHOICES = (
        ('DISPATCH', 'DISPATCH'),
        ('MONITORING', 'MONITORING'),
    )
    list_type = models.CharField(max_length=20, choices=LIST_TYPE_CHOICES)
    module = models.CharField(max_length=20, choices=MODULE_CHOICES)
    label = models.CharField(max_length=100)
    color = models.CharField(max_length=50, default='gray')
    sort_order = models.IntegerField(default=0)
    active = models.BooleanField(default=True)
    hardcoded = models.BooleanField(default=False)

    dispatch_equivalent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='equivalent_of')

    class Meta:
        unique_together = ('list_type', 'module', 'label')

    def __str__(self):
        return f"{self.module} - {self.list_type}: {self.label}"