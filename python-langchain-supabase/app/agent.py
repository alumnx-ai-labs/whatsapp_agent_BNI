"""agent.py — binds the CRM/context/calendar tools (app/tools.py) to a Gemini
model via LangChain and executes whichever tool the model decides to call.
The LLM is responsible for picking the right tool and extracting its arguments
from a natural-language instruction, rather than the app code calling the
function directly — that's the "LangChain agent with multiple tools" piece.
"""
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.tools import ALL_TOOLS

_TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = ChatGoogleGenerativeAI(
            model=os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            google_api_key=os.environ.get("GOOGLE_API_KEY"),
            temperature=0,
        ).bind_tools(ALL_TOOLS)
    return _model


def run_tool_call(instruction: str) -> dict:
    """Ask the model to satisfy `instruction` using exactly one of the bound tools,
    then execute that tool call and return its result. Raises if the model doesn't
    call a tool (e.g. instruction was ambiguous)."""
    messages = [
        SystemMessage(
            content=(
                "You are a backend action-execution agent for a CRM/calendar system. "
                "Given an instruction, call exactly one tool to satisfy it. Extract the "
                "arguments precisely from the instruction. Do not respond with prose."
            )
        ),
        HumanMessage(content=instruction),
    ]
    ai_msg = _get_model().invoke(messages)

    if not ai_msg.tool_calls:
        raise RuntimeError(f"Model did not call a tool for instruction: {instruction!r}")

    call = ai_msg.tool_calls[0]
    tool_fn = _TOOLS_BY_NAME[call["name"]]
    return tool_fn.invoke(call["args"])
