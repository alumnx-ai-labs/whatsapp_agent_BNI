"""pain_point_agent.py — LLM-based validation of a submitted business pain point
against the taxonomy in data/pain_point_taxonomy.csv. Direct Anthropic SDK call,
no framework in between.
"""
import csv
import json
import os
from pathlib import Path

import anthropic

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TAXONOMY_PATH = DATA_DIR / "pain_point_taxonomy.csv"

_taxonomy_cache = None
_client = None


def _client_instance():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


def _load_taxonomy():
    global _taxonomy_cache
    if _taxonomy_cache is None:
        with open(TAXONOMY_PATH, encoding="utf-8-sig", newline="") as f:
            _taxonomy_cache = list(csv.DictReader(f))
    return _taxonomy_cache


def _taxonomy_prompt_block() -> str:
    rows = _load_taxonomy()
    by_category: dict[str, list[str]] = {}
    for r in rows:
        by_category.setdefault(r["category"], []).append(
            f"  - {r['subtopic']}: {r['description']} (keywords: {r['example_phrases_keywords']})"
        )
    return "\n\n".join(f"{cat}:\n" + "\n".join(subs) for cat, subs in by_category.items())


def validate_pain_point(user_text: str) -> dict:
    """Returns {is_pain_point, is_clear, category, subtopic, reason}."""
    taxonomy = _taxonomy_prompt_block()

    system = f"""You are a validation agent for a business-pain-point intake bot. \
Given a customer's WhatsApp message, decide:
1) is_pain_point: does this describe a genuine business problem (operational, sales, marketing, financial, or support related)? \
General chit-chat, test messages, unrelated questions, or requests for pricing/support are NOT pain points.
2) is_clear: is there enough detail to act on (what's happening, roughly which area of the business)? \
A one-word or extremely vague statement is not clear even if it's on-topic.
3) If it is a pain point, classify it into the closest category and subtopic from this taxonomy:

{taxonomy}

Respond with ONLY valid JSON, no prose, in this exact shape:
{{"is_pain_point": boolean, "is_clear": boolean, "category": string|null, "subtopic": string|null, "reason": string}}"""

    msg = _client_instance().messages.create(
        model="claude-sonnet-5",
        max_tokens=400,
        system=system,
        messages=[{"role": "user", "content": user_text}],
    )
    text = "".join(block.text for block in msg.content if block.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "is_pain_point": False,
            "is_clear": False,
            "category": None,
            "subtopic": None,
            "reason": "validator_parse_error",
        }
