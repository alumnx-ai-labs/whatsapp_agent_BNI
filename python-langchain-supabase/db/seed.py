"""seed.py — loads the mock CRM CSV, context JSON, and taxonomy CSV into the
Supabase tables defined in schema.sql. Run this once after applying the schema,
before testing the bot end-to-end.

Usage:
    python db/seed.py
"""
import csv
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.db import get_client  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return re.sub(r"^91", "", digits)


def seed_customers():
    path = DATA_DIR / "crm_mock_customers.csv"
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    payload = [
        {
            "customer_id": r["customer_id"],
            "business_name": r["business_name"],
            "phone_number": r["phone_number"],
            "normalized_phone": normalize_phone(r["phone_number"]),
            "address": r["address"],
            "contact_person": r["contact_person"],
            "sector": r["sector"],
            "business_description": r["business_description"],
        }
        for r in rows
    ]
    get_client().table("customers").upsert(payload, on_conflict="normalized_phone").execute()
    print(f"Seeded {len(payload)} customers")


def seed_context():
    path = DATA_DIR / "customer_context_history.json"
    with open(path, encoding="utf-8") as f:
        records = json.load(f)

    payload = [
        {
            "customer_id": r["customer_id"],
            "relationship_stage": r["relationship_stage"],
            "last_interaction_date": r["last_interaction_date"],
            "total_interactions": r["total_interactions"],
            "personal_notes": r["personal_notes"],
            "pain_points_raised": r["pain_points_raised"],
            "conversation_history": r["conversation_history"],
            "suggested_greeting_hint": r["suggested_greeting_hint"],
        }
        for r in records
    ]
    get_client().table("customer_context").upsert(payload, on_conflict="customer_id").execute()
    print(f"Seeded {len(payload)} context records")


def seed_taxonomy():
    path = DATA_DIR / "pain_point_taxonomy.csv"
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    # Clear and reinsert — taxonomy has no natural unique key across re-runs.
    get_client().table("pain_point_taxonomy").delete().neq("id", 0).execute()
    get_client().table("pain_point_taxonomy").insert(rows).execute()
    print(f"Seeded {len(rows)} taxonomy rows")


if __name__ == "__main__":
    seed_customers()
    seed_context()
    seed_taxonomy()
    print("Done.")
