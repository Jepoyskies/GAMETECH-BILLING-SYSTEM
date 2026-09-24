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

