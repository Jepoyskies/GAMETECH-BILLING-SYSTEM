from django import forms
from .models import AccountType, Barangay, AddonPlan, Customer


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


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "full_name",
            "email",
            "phone",
            "address",
            "pppoe_username",
            "pppoe_password",
            "plan",
            "mikrotik_device",
            "agent",
            "barangay",
            "account_type",
            "status",
            "installation_status",
            "installed_at",
            "expires_at",
            "latitude",
            "longitude",
            "cignalplay_no",
            "cignalbox_no",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.pk:
            if "installation_status" in self.fields:
                self.fields["installation_status"].initial = "pending"
            if "status" in self.fields:
                self.fields["status"].initial = "pending"

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            email = email.strip()
            qs = Customer.objects.filter(email__iexact=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A customer with this email address already exists.")
        return email or None

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone:
            phone = phone.strip()
            qs = Customer.objects.filter(phone=phone)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A customer with this phone number already exists.")
        return phone

    def clean_pppoe_username(self):
        pppoe_username = self.cleaned_data.get("pppoe_username")
        if pppoe_username:
            pppoe_username = pppoe_username.strip()
            qs = Customer.objects.filter(pppoe_username__iexact=pppoe_username)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A customer with this PPPoE username already exists.")
        return pppoe_username or None

