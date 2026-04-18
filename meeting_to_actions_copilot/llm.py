from __future__ import annotations

import json
import os

from pydantic import ValidationError

from extract import heuristic_extract, normalize_action_item
from models import MeetingOutput


SYSTEM_PROMPT = (
    "You transform raw meeting notes into structured outputs. "
    "Return only valid JSON that matches the schema (no markdown, no code fences)."
)


def _extract_json_object(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].lstrip()

    start = stripped.find("{")
    if start == -1:
        return None

    depth = 0
    for idx in range(start, len(stripped)):
        ch = stripped[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : idx + 1]
    return None


def _schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": ["string", "null"]},
            "summary": {"type": "array", "items": {"type": "string"}},
            "decisions": {"type": "array", "items": {"type": "string"}},
            "action_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "task": {"type": "string"},
                        "owner": {"type": ["string", "null"]},
                        "due_date": {"type": ["string", "null"]},
                        "priority": {"type": ["string", "null"], "enum": ["P0", "P1", "P2", "P3", None]},
                    },
                    "required": ["task"],
                },
            },
        },
        "required": ["summary", "decisions", "action_items"],
    }


def _build_user_prompt(text: str) -> str:
    schema = json.dumps(_schema(), ensure_ascii=False)
    return (
        "Extract a concise summary (5 bullets max), decisions, and action items from the meeting notes. "
        "For action items, prefer explicit owners and due dates if present; otherwise null. "
        "Priority should be one of P0/P1/P2/P3 or null. "
        "Return ONLY JSON matching this JSON Schema:\n"
        + schema
        + "\n\nMeeting notes:\n"
        + text
    )


def extract_with_llm(text: str, model: str = "claude-3-5-sonnet-latest") -> MeetingOutput:
    out, _raw = extract_with_llm_with_raw(text=text, model=model)
    out.action_items = [normalize_action_item(a) for a in out.action_items]
    return out


def extract_with_llm_with_raw(text: str, model: str = "claude-3-5-sonnet-latest") -> tuple[MeetingOutput, str]:
    openai_key = os.getenv("OPENAI_API_KEY")
    openai_base_url = os.getenv("OPENAI_BASE_URL")
    if openai_key and openai_base_url:
        try:
            from openai import OpenAI
        except Exception:
            return heuristic_extract(text)

        client = OpenAI(api_key=openai_key, base_url=openai_base_url)

        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(text)},
            ],
        )

        content = (resp.choices[0].message.content or "").strip()
        json_text = _extract_json_object(content) or content
        try:
            parsed = json.loads(json_text)
        except Exception:
            return heuristic_extract(text), content

        try:
            out = MeetingOutput.model_validate(parsed)
            out.action_items = [normalize_action_item(a) for a in out.action_items]
            return out, content
        except ValidationError:
            return heuristic_extract(text), content

    if not os.getenv("ANTHROPIC_API_KEY"):
        return heuristic_extract(text), ""

    try:
        from anthropic import Anthropic
    except Exception:
        return heuristic_extract(text), ""

    client = Anthropic()

    msg = client.messages.create(
        model=model,
        max_tokens=1200,
        temperature=0.2,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(text)}],
    )

    content = msg.content[0].text if msg.content else ""
    json_text = _extract_json_object(content) or content
    try:
        parsed = json.loads(json_text)
    except Exception:
        return heuristic_extract(text), content

    try:
        out = MeetingOutput.model_validate(parsed)
        out.action_items = [normalize_action_item(a) for a in out.action_items]
        return out, content
    except ValidationError:
        return heuristic_extract(text), content
