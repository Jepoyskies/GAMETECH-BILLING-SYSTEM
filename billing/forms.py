from django import forms
from .models import AccountType, Barangay

class AccountTypeForm(forms.ModelForm):
    class Meta:
        model = AccountType
        fields = ['type_name']
        widgets = {
            'type_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter account type name...'}),
        }

class BarangayForm(forms.ModelForm):
    class Meta:
        model = Barangay
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter barangay name...'}),
        }
