from django import forms
from .models import MonitoringRecord, DispatchRecord, ConfigOption, Technician, JobDetail

class DispatchRecordForm(forms.ModelForm):
    teams = forms.ModelMultipleChoiceField(
        queryset=Technician.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select select2'}),
        required=False
    )

    class Meta:
        model = DispatchRecord
        fields = [
            'source_tab', 'date', 'client_name', 'address', 'contact_number',
            'concern', 'sales_agent', 'ticket_number', 'status_option',
            'type_option', 'chat_type_option', 'teams', 'remarks'
        ]
        widgets = {
            'source_tab': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'client_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'concern': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'sales_agent': forms.TextInput(attrs={'class': 'form-control'}),
            'ticket_number': forms.TextInput(attrs={'class': 'form-control'}),
            'status_option': forms.Select(attrs={'class': 'form-select'}),
            'type_option': forms.Select(attrs={'class': 'form-select'}),
            'chat_type_option': forms.Select(attrs={'class': 'form-select'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter ConfigOptions based on module=MONITORING
        self.fields['status_option'].queryset = ConfigOption.objects.filter(module='MONITORING', list_type='STATUS', active=True)
        self.fields['type_option'].queryset = ConfigOption.objects.filter(module='MONITORING', list_type='TYPE', active=True)
        self.fields['chat_type_option'].queryset = ConfigOption.objects.filter(module='MONITORING', list_type='CHAT_TYPE', active=True)


class MonitoringRecordForm(forms.ModelForm):
    teams = forms.ModelMultipleChoiceField(
        queryset=Technician.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select select2'}),
        required=False
    )

    class Meta:
        model = MonitoringRecord
        fields = [
            'tab_type', 'date', 'client_name', 'address', 'contact_number',
            'concern', 'sales_agent', 'ticket_number', 'status_option',
            'type_option', 'chat_type_option', 'teams', 'remarks'
        ]
        widgets = {
            'tab_type': forms.HiddenInput(),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'client_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'concern': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'sales_agent': forms.TextInput(attrs={'class': 'form-control'}),
            'ticket_number': forms.TextInput(attrs={'class': 'form-control'}),
            'status_option': forms.Select(attrs={'class': 'form-select'}),
            'type_option': forms.Select(attrs={'class': 'form-select'}),
            'chat_type_option': forms.Select(attrs={'class': 'form-select'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter ConfigOptions based on module=MONITORING
        self.fields['status_option'].queryset = ConfigOption.objects.filter(module='MONITORING', list_type='STATUS', active=True)
        self.fields['type_option'].queryset = ConfigOption.objects.filter(module='MONITORING', list_type='TYPE', active=True)
        self.fields['chat_type_option'].queryset = ConfigOption.objects.filter(module='MONITORING', list_type='CHAT_TYPE', active=True)

class JobDetailForm(forms.ModelForm):
    class Meta:
        model = JobDetail
        fields = [
            'schedule_date', 'schedule_time', 'barangay_city', 'account_no', 
            'job_order', 'email_address', 'nap_port', 'cable_length', 
            'nap_reading', 'pole_number', 'plan_package', 'ont_modem_sn', 
            'signal_level', 'facility', 'house_reading', 'special_instruction', 
            'technician_remarks', 'acknowledged_by'
        ]
        widgets = {
            'schedule_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'schedule_time': forms.TextInput(attrs={'class': 'form-control'}),
            'barangay_city': forms.TextInput(attrs={'class': 'form-control'}),
            'account_no': forms.TextInput(attrs={'class': 'form-control'}),
            'job_order': forms.TextInput(attrs={'class': 'form-control'}),
            'email_address': forms.EmailInput(attrs={'class': 'form-control'}),
            'nap_port': forms.TextInput(attrs={'class': 'form-control'}),
            'cable_length': forms.TextInput(attrs={'class': 'form-control'}),
            'nap_reading': forms.TextInput(attrs={'class': 'form-control'}),
            'pole_number': forms.TextInput(attrs={'class': 'form-control'}),
            'plan_package': forms.TextInput(attrs={'class': 'form-control'}),
            'ont_modem_sn': forms.TextInput(attrs={'class': 'form-control'}),
            'signal_level': forms.TextInput(attrs={'class': 'form-control'}),
            'facility': forms.TextInput(attrs={'class': 'form-control'}),
            'house_reading': forms.TextInput(attrs={'class': 'form-control'}),
            'special_instruction': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'technician_remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'acknowledged_by': forms.TextInput(attrs={'class': 'form-control'}),
        }
