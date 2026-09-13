from django import forms
from .models import AccountType, Barangay, AddonPlan


class AccountTypeForm(forms.ModelForm):
    class Meta:
        model = AccountType
        fields = ["type_name"]
        widgets = {
            "type_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter account type name...",
                }
            ),
        }


class BarangayForm(forms.ModelForm):
    class Meta:
        model = Barangay
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Enter barangay name..."}
            ),
        }


class AddonPlanForm(forms.ModelForm):
    class Meta:
        model = AddonPlan
        fields = [
            "name",
            "addon_type",
            "duration_days",
            "price",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Cignal Play Premium 30-Day",
                    "required": "required",
                }
            ),
            "addon_type": forms.Select(
                attrs={
                    "class": "form-select",
                    "required": "required",
                }
            ),
            "duration_days": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "30",
                    "min": "1",
                    "required": "required",
                }
            ),
            "price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "150.00",
                    "step": "0.01",
                    "min": "0",
                    "required": "required",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Optional details or inclusions...",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }
