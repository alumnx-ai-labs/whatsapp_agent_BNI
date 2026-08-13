"""pain_point_agent.py — LangChain version. Uses ChatAnthropic.with_structured_output(),
which under the hood is Anthropic's forced tool-calling for schema-constrained output —
so even this "reasoning" step is a LangChain tool-calling mechanism, just an implicit one
rather than an explicit @tool like lookup_customer/book_calendar_meeting.
"""
import csv
import os
from pathlib import Path
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TAXONOMY_PATH = DATA_DIR / "pain_point_taxonomy.csv"

_taxonomy_cache = None
_structured_model = None


class PainPointValidation(BaseModel):
    is_pain_point: bool = Field(description="Does this describe a genuine business problem?")
    is_clear: bool = Field(description="Is there enough detail to act on?")
    category: Optional[str] = Field(default=None, description="Matched taxonomy category, if any")
    subtopic: Optional[str] = Field(default=None, description="Matched taxonomy subtopic, if any")
    reason: str = Field(description="Brief justification for the judgment")


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


def _get_structured_model():
    global _structured_model
    if _structured_model is None:
        model = ChatAnthropic(model="claude-sonnet-5", api_key=os.environ.get("ANTHROPIC_API_KEY"))
        _structured_model = model.with_structured_output(PainPointValidation)
    return _structured_model


def validate_pain_point(user_text: str) -> dict:
    taxonomy = _taxonomy_prompt_block()
    system = f"""You are a validation agent for a business-pain-point intake bot. \
Given a customer's WhatsApp message, decide:
1) is_pain_point: does this describe a genuine business problem (operational, sales, marketing, financial, or support related)? \
General chit-chat, test messages, unrelated questions, or requests for pricing/support are NOT pain points.
2) is_clear: is there enough detail to act on (what's happening, roughly which area of the business)? \
A one-word or extremely vague statement is not clear even if it's on-topic.
3) If it is a pain point, classify it into the closest category and subtopic from this taxonomy:

{taxonomy}"""

    result: PainPointValidation = _get_structured_model().invoke(
        [SystemMessage(content=system), HumanMessage(content=user_text)]
    )
    return result.model_dump()
