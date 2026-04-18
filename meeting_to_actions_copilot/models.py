from __future__ import annotations

from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    task: str = Field(min_length=1)
    owner: str = "Unassigned"
    due_date: str | None = None
    priority: str | None = None


class MeetingOutput(BaseModel):
    title: str | None = None
    summary: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
