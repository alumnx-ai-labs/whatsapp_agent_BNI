"""phone_utils.py — shared phone-number normalization.

Split out of the old crm_data.py so crm_lookup.py and crm_registration.py
(owned by different people) never need to import each other or edit the
same file.
"""
import re


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return re.sub(r"^91", "", digits)
