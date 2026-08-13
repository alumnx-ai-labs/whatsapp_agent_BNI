"""crm.py — customer lookup against the mock CRM CSV (data/crm_mock_customers.csv)."""
import csv
import re
import time
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CRM_PATH = DATA_DIR / "crm_mock_customers.csv"

_cache = None


def _load_crm():
    global _cache
    if _cache is None:
        with open(CRM_PATH, encoding="utf-8-sig", newline="") as f:
            _cache = list(csv.DictReader(f))
    return _cache


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return re.sub(r"^91", "", digits)


def find_customer_by_phone(phone: str) -> Optional[dict]:
    target = normalize_phone(phone)
    for row in _load_crm():
        if normalize_phone(row["phone_number"]) == target:
            return row
    return None


def register_new_customer(phone: str, name: str, business_name: str) -> dict:
    # In production this would INSERT into the real CRM/database.
    print(f"[crm] would create new record: {name} / {business_name} / {phone}")
    return {
        "customer_id": f"NEW_{int(time.time() * 1000)}",
        "business_name": business_name,
        "phone_number": phone,
        "contact_person": name,
        "sector": "unclassified",
        "business_description": "",
    }
