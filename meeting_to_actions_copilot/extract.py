from __future__ import annotations

import csv
import io
import re
from datetime import date

from models import ActionItem, MeetingOutput


_ACTION_PREFIX_RE = re.compile(r"^(action|todo|to do|follow up|next step)\s*[:\-]\s*", re.I)
_OWNER_TO_RE = re.compile(r"^([A-Z][\w]*(?:\s+[A-Z][\w]*){0,2})\s+to\s+(.*)$")
_OWNER_KV_RE = re.compile(r"\b(owner|assignee|assigned to)\s*[:\-]\s*([^;,.]+)", re.I)
_PRIORITY_RE = re.compile(r"\bpriority\s*(p[0-3])\b|\b(p[0-3])\b", re.I)
_DUE_RE = re.compile(r"\b(due|by)\s*[:\-]?\s*([^;,.]+)", re.I)
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def extract_owner(text: str) -> str:
    match = _OWNER_TO_RE.match(text.strip())
    if match:
        return match.group(1).strip()

    kv = _OWNER_KV_RE.search(text)
    if kv:
        return kv.group(2).strip()

    return "Unassigned"


def extract_priority(text: str) -> str | None:
    match = _PRIORITY_RE.search(text)
    if not match:
        return None
    value = (match.group(1) or match.group(2) or "").upper()
    return value if value in {"P0", "P1", "P2", "P3"} else None


def extract_due_date(text: str) -> str | None:
    iso = _ISO_DATE_RE.search(text)
    if iso:
        return iso.group(0)

    match = _DUE_RE.search(text)
    if match:
        return match.group(2).strip()
    return None


def clean_task_text(text: str) -> str:
    cleaned = _ACTION_PREFIX_RE.sub("", text).strip()
    m = _OWNER_TO_RE.match(cleaned)
    if m:
        cleaned = m.group(2).strip()

    cleaned = _PRIORITY_RE.sub("", cleaned)
    cleaned = _DUE_RE.sub("", cleaned)
    cleaned = cleaned.strip(" -;,.()")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_action_item(item: ActionItem) -> ActionItem:
    owner = (item.owner or "").strip() or "Unassigned"
    priority = (item.priority or "").strip().upper() or None
    if priority and priority not in {"P0", "P1", "P2", "P3"}:
        priority = None
    return ActionItem(task=item.task.strip(), owner=owner, due_date=item.due_date, priority=priority)


def extract_pain_points(text: str) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines()]
    pain_points: list[str] = []

    in_section = False
    for raw in lines:
        line = raw.strip()
        if not line:
            if in_section:
                break
            continue

        lowered = line.lower()
        if lowered.startswith("pain points") or lowered.startswith("pain point"):
            in_section = True
            continue

        if in_section:
            if line.startswith("-") or line.startswith("•"):
                pain_points.append(line.lstrip("-• ").strip())
            else:
                if len(pain_points) >= 3:
                    break
                pain_points.append(line)

    if pain_points:
        return pain_points[:10]

    for raw in lines:
        line = raw.strip()
        if line.startswith("-") or line.startswith("•"):
            val = line.lstrip("-• ").strip()
            if val.lower().startswith("pain"):
                pain_points.append(val)

    return pain_points[:10]


def map_pain_points(
    pain_points: list[str],
    decisions: list[str],
    action_items: list[ActionItem],
) -> list[dict]:
    def tokens(s: str) -> set[str]:
        words = re.findall(r"[a-zA-Z]{3,}", s.lower())
        return set(words)

    decision_tokens = [(d, tokens(d)) for d in decisions]
    action_tokens = [(a, tokens(a.task)) for a in action_items]

    mappings: list[dict] = []
    for pain in pain_points:
        pain_toks = tokens(pain)
        related_decisions = [d for d, t in decision_tokens if len(pain_toks & t) >= 2]
        related_actions = [a for a, t in action_tokens if len(pain_toks & t) >= 2]
        mappings.append(
            {
                "pain_point": pain,
                "decisions": related_decisions[:5],
                "actions": related_actions[:5],
            }
        )

    if not mappings and (decisions or action_items):
        mappings.append(
            {
                "pain_point": "General",
                "decisions": decisions[:5],
                "actions": action_items[:5],
            }
        )

    return mappings


def heuristic_extract(text: str) -> MeetingOutput:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    action_items: list[ActionItem] = []
    decisions: list[str] = []

    action_markers = (
        "action:",
        "todo:",
        "to do:",
        "follow up:",
        "next step:",
        "we will",
        "let's",
        "please",
        "assigned",
    )

    decision_markers = ("decision:", "decided:", "we decided", "agree to", "approved")

    for line in lines:
        lowered = line.lower()

        if any(m in lowered for m in decision_markers):
            decisions.append(line)

        if any(lowered.startswith(m) for m in action_markers) or any(m in lowered for m in action_markers):
            owner = extract_owner(_ACTION_PREFIX_RE.sub("", line).strip())
            due_date = extract_due_date(line)
            priority = extract_priority(line)
            task = clean_task_text(line)
            if task:
                action_items.append(
                    ActionItem(task=task, owner=owner, due_date=due_date, priority=priority)
                )

    summary = []
    if lines:
        summary = [lines[0][:140]]
        if len(lines) > 1:
            summary.append(lines[1][:140])

    return MeetingOutput(
        title=f"Meeting Notes ({date.today().isoformat()})",
        summary=summary,
        decisions=decisions[:10],
        action_items=[normalize_action_item(a) for a in action_items[:25]],
    )


def to_markdown(out: MeetingOutput) -> str:
    parts: list[str] = []
    if out.title:
        parts.append(f"# {out.title}")

    parts.append("## AI Summary")
    if out.summary:
        parts.extend([f"- {s}" for s in out.summary])
    else:
        parts.append("- (none)")

    parts.append("## Key Decisions")
    if out.decisions:
        parts.extend([f"- {d}" for d in out.decisions])
    else:
        parts.append("- (none)")

    parts.append("## Action Items")
    if out.action_items:
        parts.append("| Task | Owner | Due Date | Priority |")
        parts.append("|---|---|---|---|")
        for item in out.action_items:
            parts.append(
                "| "
                + " | ".join(
                    [
                        (item.task or "").replace("|", "\\|"),
                        (item.owner or "").replace("|", "\\|"),
                        (item.due_date or "").replace("|", "\\|"),
                        (item.priority or "").replace("|", "\\|"),
                    ]
                )
                + " |"
            )
    else:
        parts.append("- (none)")

    return "\n".join(parts).strip() + "\n"


def to_csv_bytes(out: MeetingOutput) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["task", "owner", "due_date", "priority"])
    for item in out.action_items:
        writer.writerow([item.task, item.owner or "", item.due_date or "", item.priority or ""])
    return buffer.getvalue().encode("utf-8")
