"""
Password policy validators and temporary credential generators for Gametech Unli Fiber.
Enforces Phase 1 Security Standards across all login personas (portal, agent, technician, staff).
"""

import re
import secrets
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.utils import timezone

# Common weak passwords blacklist
COMMON_PASSWORDS = {
    "password", "password123", "password1234", "1234567890", "123456789",
    "12345678", "admin12345", "gametech123", "gametech2024", "gametech2025",
    "gametech2026", "internet123", "p@ssword", "p@ssword1", "welcome123",
    "qwertyuiop", "iloveyou123", "letmein1234"
}

# Unambiguous alphabet excluding look-alike characters (0/O, 1/l/I)
UNAMBIGUOUS_LETTERS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
UNAMBIGUOUS_DIGITS = "23456789"
SPECIAL_CHARS = "!@#$%^&*()-_=+[]{}|;:,.<>?"


def validate_password_policy(password, user_or_customer=None, identifier=None):
    """
    Enforces Gametech Global Password Policy:
    1. Minimum 10 characters
    2. At least one letter
    3. At least one number
    4. At least one special character
    5. Not on the common password blacklist
    6. Not equal to username, phone number, or full name
    """
    if not password or len(password) < 10:
        raise ValidationError("Password must be at least 10 characters long.")

    if not re.search(r"[A-Za-z]", password):
        raise ValidationError("Password must contain at least one letter.")

    if not re.search(r"\d", password):
        raise ValidationError("Password must contain at least one number.")

    if not any(char in SPECIAL_CHARS for char in password):
        raise ValidationError("Password must contain at least one special character (e.g. !@#$%^&*).")

    if password.lower() in COMMON_PASSWORDS:
        raise ValidationError("This password is too common. Please choose a stronger password.")

    # Disallow passwords matching username or phone
    check_values = []
    if identifier:
        check_values.append(str(identifier).lower())

    if user_or_customer:
        if hasattr(user_or_customer, "username") and user_or_customer.username:
            check_values.append(user_or_customer.username.lower())
        if hasattr(user_or_customer, "phone") and user_or_customer.phone:
            check_values.append(user_or_customer.phone.lower())
            # Also check phone without leading zero or country code
            clean_phone = re.sub(r"\D", "", user_or_customer.phone)
            if clean_phone:
                check_values.append(clean_phone)
        if hasattr(user_or_customer, "pppoe_username") and user_or_customer.pppoe_username:
            check_values.append(user_or_customer.pppoe_username.lower())
        if hasattr(user_or_customer, "full_name") and user_or_customer.full_name:
            check_values.append(user_or_customer.full_name.lower())

    pw_lower = password.lower()
    for val in check_values:
        if val and (pw_lower == val or val in pw_lower):
            raise ValidationError("Password must not contain or match your username, full name, or phone number.")


def generate_temp_password(length=10):
    """
    Generates a cryptographically random temporary password:
    - Exactly length characters (default 10)
    - Mixed letters and numbers
    - Avoids look-alike characters (0/O, 1/l/I)
    - Valid for 7 days
    """
    # Guarantee at least 2 letters, 2 digits, and fill the rest
    chosen = [
        secrets.choice(UNAMBIGUOUS_LETTERS),
        secrets.choice(UNAMBIGUOUS_LETTERS),
        secrets.choice(UNAMBIGUOUS_DIGITS),
        secrets.choice(UNAMBIGUOUS_DIGITS),
    ]
    combined_pool = UNAMBIGUOUS_LETTERS + UNAMBIGUOUS_DIGITS
    for _ in range(length - len(chosen)):
        chosen.append(secrets.choice(combined_pool))

    # Shuffle securely
    for i in range(len(chosen) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chosen[i], chosen[j] = chosen[j], chosen[i]

    return "".join(chosen)


def is_temp_password_expired(temp_created_at, max_days=7):
    """
    Checks if a temporary password has exceeded its validity period (default 7 days).
    """
    if not temp_created_at:
        return False
    return timezone.now() > temp_created_at + timedelta(days=max_days)


def normalize_ph_phone(phone, required=True):
    """
    Validates and normalizes Philippine mobile numbers to the canonical 11-digit format: 09XXXXXXXXX.
    Accepts:
    - 09XXXXXXXXX (11 digits)
    - +639XXXXXXXXX (13 chars)
    - 639XXXXXXXXX (12 digits)
    - 9XXXXXXXXX (10 digits)
    Returns:
    - Canonical string '09XXXXXXXXX'
    Raises:
    - ValidationError if format is invalid.
    If required=False and input is empty/None, returns None.
    """
    if not phone:
        if required:
            raise ValidationError("Mobile phone number is required.")
        return None

    cleaned = re.sub(r"[\s\-\(\)\.]", "", str(phone))

    if cleaned.startswith("+63"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("63"):
        cleaned = "0" + cleaned[2:]
    elif cleaned.startswith("9") and len(cleaned) == 10:
        cleaned = "0" + cleaned

    if not re.match(r"^09\d{9}$", cleaned):
        raise ValidationError(
            f"Invalid Philippine mobile number '{phone}'. Expected format: 09XXXXXXXXX or +639XXXXXXXXX."
        )

    return cleaned


def normalize_text_key(text):
    """
    Normalizes a text string (name or address) for duplicate detection:
    Replaces common punctuation delimiters with spaces, lowercases, strips other symbols,
    and collapses multiple whitespace characters.
    """
    if not text:
        return ""
    # Treat common address/name delimiters like hyphens, slashes, commas, and dots as word breaks
    delimiters_spaced = re.sub(r"[-/,.]", " ", str(text).lower())
    cleaned = re.sub(r"[^\w\s]", "", delimiters_spaced)
    return " ".join(cleaned.split())


def check_customer_or_prospect_duplicate(
    phone=None,
    full_name=None,
    address=None,
    exclude_prospect_id=None,
    exclude_customer_id=None,
):
    """
    Detects duplicate records across Customer and Prospect tables:
    1. Exact Philippine phone match
    2. Case, spacing, and punctuation-insensitive normalized Name + Address match
    Returns: (is_duplicate: bool, reason_or_match_text: str or None, matched_obj: object or None)
    """
    from billing.models import Customer, Prospect

    # 1. Check Phone
    if phone:
        norm_phone = normalize_ph_phone(phone, required=False) or str(phone).strip()
        if norm_phone:
            # Check existing customers
            cust_qs = Customer.objects.filter(phone=norm_phone)
            if exclude_customer_id:
                cust_qs = cust_qs.exclude(id=exclude_customer_id)
            match_cust = cust_qs.first()
            if match_cust:
                return (
                    True,
                    f"Matches existing subscriber: {match_cust.full_name} ({match_cust.phone})",
                    match_cust,
                )

            # Check existing prospects
            prosp_qs = Prospect.objects.filter(phone=norm_phone).exclude(status__in=["declined", "converted"])
            if exclude_prospect_id:
                prosp_qs = prosp_qs.exclude(id=exclude_prospect_id)
            match_prosp = prosp_qs.first()
            if match_prosp:
                agent_name = match_prosp.agent.name if match_prosp.agent else "Direct"
                return (
                    True,
                    f"Duplicate phone '{norm_phone}' matches referral lead: {match_prosp.full_name} (Agent: {agent_name}, Status: {match_prosp.get_status_display()})",
                    match_prosp,
                )

    # 2. Check Normalized Name + Address
    if full_name and address:
        target_name_key = normalize_text_key(full_name)
        target_addr_key = normalize_text_key(address)

        if target_name_key and target_addr_key:
            # Check customers
            cust_qs = Customer.objects.all()
            if exclude_customer_id:
                cust_qs = cust_qs.exclude(id=exclude_customer_id)
            for c in cust_qs.only("id", "full_name", "address"):
                if normalize_text_key(c.full_name) == target_name_key and normalize_text_key(c.address) == target_addr_key:
                    return (
                        True,
                        f"Duplicate name and address matches existing subscriber: {c.full_name} at {c.address} (ID #{c.id})",
                        c,
                    )

            # Check prospects
            prosp_qs = Prospect.objects.exclude(status__in=["declined", "converted"])
            if exclude_prospect_id:
                prosp_qs = prosp_qs.exclude(id=exclude_prospect_id)
            for p in prosp_qs.only("id", "full_name", "address", "agent"):
                if normalize_text_key(p.full_name) == target_name_key and normalize_text_key(p.address) == target_addr_key:
                    agent_name = p.agent.name if p.agent else "Direct"
                    return (
                        True,
                        f"Duplicate name and address matches referral lead: {p.full_name} at {p.address} (Agent: {agent_name})",
                        p,
                    )

    return False, None, None

